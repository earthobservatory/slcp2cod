#!/usr/bin/env python
'''
Queries ElasticSearch for SLCPs over and AOI, builds list of SLCP pairs, & Submits COD jobs
'''

from __future__ import print_function
from __future__ import division
from builtins import str
from past.utils import old_div
import sys
import os
import json
import logging
import requests
import argparse
import pytz
import hashlib
from hysds.celery import app
from dateutil import parser
from datetime import timedelta

from celery import Celery
from hysds_commons.job_utils import submit_mozart_job


def main(slcp_version, aoi_name, dataset_tag=None, project=None, queue=None, priority=None):
    '''
    Queries the AOI for time & coordinate ranges, then determines proper SLCP co-event & pre-event pairs,
    then submits COD jobs for those pairs
    '''
    #determine coords & event time from aoi_name
    print('Determining proper SLCP pairs over {}'.format(aoi_name))
    aoi_template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'aoi_template.json')
    aoi_template = json.load(open(aoi_template_path))
    aoi_template['query']['bool']['must'][1]['query_string']['query'] = '"{0}"'.format(aoi_name)
    results = search(endpoint='grq', params=aoi_template)
    aoi_dict = results['hits']['hits'][0]['_source']
    coords = aoi_dict['location']['coordinates']
    aoi_event_time = get_event_time(aoi_dict)
    aoi_event_dt = parser.parse(aoi_event_time)
    ctx = load_context()
    try:
        aoi_start_time = parser.parse(walk(aoi_dict, 'starttime')).replace(tzinfo=pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except:
        raise Exception('unable to parse starttime from AOI: {}'.format(aoi_name))
    try:
        aoi_end_time = parser.parse(walk(aoi_dict, 'endtime')).replace(tzinfo=pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except:
        raise Exception('unable to parse endtime from AOI: {}'.format(aoi_name))

    template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'query_template.json')
    template = json.load(open(template_path))
    #get all slcps that contain start and end in the time window
    template['query']['filtered']['query']['bool']['must'][1]['term']['system_version.raw'] = slcp_version
    template['query']['filtered']['query']['bool']['should'][0]['range']['starttime']['from'] = aoi_start_time
    template['query']['filtered']['query']['bool']['should'][0]['range']['starttime']['to'] = aoi_end_time
    template['query']['filtered']['query']['bool']['should'][1]['range']['endtime']['from'] = aoi_start_time
    template['query']['filtered']['query']['bool']['should'][1]['range']['endtime']['to'] = aoi_end_time
    template['query']['filtered']['filter']['geo_shape']['location']['shape']['coordinates'] = coords
    if ctx['track_number']:
        template['query']['filtered']['query']['bool']['must'].append({"term": {"metadata.trackNumber": ctx['track_number']}})
    #determine grq index
    index = 'grq_{0}_s1-slcp'.format(slcp_version)
    #run query for slcp products covering the aoi
    results = search(endpoint='grq', params=template, index=index)
    minmatch = 0
    if 'minmatch' in list(ctx.keys()):
        minmatch = int(ctx['minmatch'])
    min_overlap = 0.0
    if 'min_overlap' in list(ctx.keys()):
        min_overlap = float(ctx['min_overlap'])

    if ctx['overriding_azimuth_looks']:
        azimuth_lks = [x.strip() for x in ctx['overriding_azimuth_looks'].split(",")];
        if len(azimuth_lks) < 3:
            azimuth_lks = None
    else:
        azimuth_lks = None

    if ctx['overriding_range_looks']:
        range_lks = [x.strip() for x in ctx['overriding_range_looks'].split(",")];
        if len(range_lks) < 3:
            range_lks = None
    else:
        range_lks = None

    #print('slcp results: {0}'.format(results))
    valid_pairs = determine_valid_pairs(results, aoi_event_dt, minmatch, min_overlap)

    if len(valid_pairs) > 0:
        print('submitting COD jobs...')
    else:
        print('no COD jobs to submit.')

    for x in valid_pairs:
        url_list = (x[0]['url'], x[1]['url'])
        swath = int(x[1]['swath'])
        az_lk = azimuth_lks[swath-1] if azimuth_lks else ""
        rn_lk = range_lks[swath-1] if range_lks else ""
        submit_cod_job(url_list, aoi_name, dataset_tag, project, queue, priority, az_lk, rn_lk)

def load_context():
    '''loads context from the workdir'''
    with open('_context.json') as data_file:
        data = json.load(data_file)
        return data

def load_job_json():
    '''loads job.json from the workdir'''
    with open('_job.json') as data_file:
        data = json.load(data_file)
        return data

def get_event_time(aoi_dict):
    '''determines the event time from the aoi dict and returns it as a datetime'''
    for item in ['event_time', 'eventtime', 'event']:
        event_time = walk(aoi_dict, item)
        if item == 'event' and type(event_time) is dict and 'time' in list(event_time.keys()):
            event_time = event_time['time'] # handle the ['event']['time'] case
        if event_time:
            return parser.parse(event_time).replace(tzinfo=pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return None

def walk(node, key_match):
    '''recursive node walk, returns None if nothing found, returns the value if a key matches key_match'''
    if isinstance(node, dict):
        for key, item in list(node.items()):
            if str(key) == str(key_match):
                return item
            result = walk(item, key_match)
            if not result is None:
                return result
        return None
    if isinstance(node, list):
        for item in node:
            if isinstance(item, dict) or isinstance(item, list):
                result = walk(item, key_match)
                if not result is None:
                    return result
        return None
    return None

def determine_valid_pairs(slcp_dict, event_dt, minmatch, min_overlap):
    '''
    Determines which SLCP pairs are valid co-event pairs
    returns a list of s3 url pairs that match
    '''
    print('AOI Event time: {0}'.format(event_dt))
    pre_events = [] #list of pre-event pairs
    co_events = [] #list of co-event pairs
    for slcp in slcp_dict['hits']['hits']:
        slcp_struct = build_slcp_struct(slcp)
        if slcp_struct['end'] < event_dt:
            pre_events.append(slcp_struct)
            #print('{} starttime:{}, endtime:{}, track:{}, swath:{}, type:{}'.format(slcp_uid, start, end, track_num, swath, 'pre-event'))
        elif slcp_struct['start'] < event_dt and slcp_struct['end'] > event_dt:
            co_events.append(slcp_struct)
            #print('{} starttime:{}, endtime:{}, track:{}, swath:{}, type:{}'.format(slcp_uid, start, end, track_num, swath, 'co-event'))
    print('Found {0} pre-event slcps and {1} co-event slcps'.format(len(pre_events), len(co_events)))
    #determine pairs that share start & end
    valid_pairs = []
    #print statement for lists
    print('Pre-event SLCPs\n----------------')
    [print('{} track:{} frame:{} orbit:{} swath:{}'.format(item['uid'], item['track'], item['frame'], item['orbit'], item['swath'])) for item in pre_events]
    print('Co-event SLCPs\n----------------')
    [print('{} track:{} frame:{} orbit:{} swath:{}'.format(item['uid'], item['track'], item['frame'], item['orbit'], item['swath'])) for item in co_events]
    #find all the pairs that match frame track and swath where min_overlap is not satisfied
    print('Finding matching pairs...')
    for pre_slcp in pre_events:
        for co_slcp in co_events:
            if match_slcps(pre_slcp, co_slcp, min_overlap):
                baseline = (co_slcp['end'] - pre_slcp['start']).total_seconds() / 86400.0
                pre_slcp['baseline'] = baseline
                co_slcp['baseline'] = baseline
                print('Found match pre-event slcp: {} to co-event slcp: {}'.format(pre_slcp['uid'], co_slcp['uid']))
                print('Track: {0}, orbit: {1}, frame: {2}, swath: {3}'.format(co_slcp['track'], co_slcp['orbit'], co_slcp['frame'], co_slcp['swath']))
                valid_pairs.append( (pre_slcp, co_slcp) )
    print('Found {} valid pairs that match co-event scenes.'.format(len(valid_pairs)))
    if len(valid_pairs) == 0:
        return []
    if minmatch > 0:
        valid_pairs = minmatch_filter(valid_pairs, minmatch)
    else:
        print('Not using minmatch, submitting all SLCP pairs.')
    print('Submitting {0} COD jobs for matching SLCP pairs'.format(len(valid_pairs)))
    [print('{} : {} frame:{} track: {}, swath: {} baseline: {}'.format(x[0]['uid'], x[1]['uid'], x[1]['track'], x[1]['frame'], x[1]['swath'], x[1]['baseline'])) for x in valid_pairs]
    return valid_pairs

def build_slcp_struct(slcp):
    '''builds a structure of relevant metadata per slcp & returns it as a dict'''
    start, end = get_start_end_datetimes(slcp)
    url = get_url(slcp)
    track_num = slcp['_source']['metadata']['trackNumber']
    orbit_num = slcp['_source']['metadata']['orbitNumber']
    frame_id = slcp['_source']['metadata']['frameID']
    swath = slcp['_source']['metadata']['swath']
    if type(swath) is list:
        swath = swath[0]
    location = slcp['_source']['location']
    slcp_uid = slcp['_id']
    return {'uid': slcp_uid, 'location': location, 'start': start, 'end': end, 'swath': swath, 'url': url, 'track': track_num, 'orbit': orbit_num[0], 'frame': frame_id}

def minmatch_filter(valid_pairs, minmatch):
    '''filter a list of valid pair slcp tuples into proper list eliminiating matches over minmatch count'''
    print('Filtering using minmatch {} for each swath matching frame and track'.format(minmatch))
    #valid_pairs = sorted(valid_pairs, key = lambda x: x[0]['baseline'], reverse = False)
    submission_pairs = {}
    for item in valid_pairs:
        track = item[1]['track']
        frame = item[1]['frame']
        swath = item[1]['swath']
        #baseline = item[1]['baseline']
        key = '{}_{}_{}'.format(track,frame,swath)
        if not key in list(submission_pairs.keys()):
            submission_pairs[key] = [item]
        else:
            submission_pairs[key].append(item) 
    valid_pairs = []
    for key in list(submission_pairs.keys()):
         valid_list = sorted(submission_pairs[key], key = lambda x: x[0]['baseline'])
         valid_list = valid_list[:minmatch]
         valid_pairs.extend(valid_list)
    return valid_pairs

def match_slcps(pre_slcp, co_slcp, min_overlap):
    '''
    Determines if slcps are a proper match. Returns True if a match, False otherwise
    '''
    #make sure track, frames, & swath match
    if not (co_slcp['track'] == pre_slcp['track'] and co_slcp['orbit'] == pre_slcp['orbit'] and co_slcp['frame'] == pre_slcp['frame'] and co_slcp['swath'] == pre_slcp['swath']):
        return False
    #co-event start should match pre-event endn (within 24 hours)
    delta = pre_slcp['end'] - co_slcp['start']
    if not abs(delta.total_seconds()) < 86400:
        return False
    overlap = get_overlap(pre_slcp, co_slcp)
    if overlap < min_overlap:
        print('{} and {} fail to match due to overlap of {}. (minimum is {})'.format(pre_slcp['uid'], co_slcp['uid'], overlap, min_overlap))
        return False
    return True

def get_overlap(pre_slcp, co_slcp):
    '''
    Returns the overlap percentage (0-1) of the latitude bands for the SLCPs, compared to the co_event SLCP
    '''
    min_pre_slcp = min([float(x[1]) for x in pre_slcp['location']['coordinates'][0]])
    max_pre_slcp = max([float(x[1]) for x in pre_slcp['location']['coordinates'][0]])
    min_co_slcp = min([float(x[1]) for x in co_slcp['location']['coordinates'][0]])    
    max_co_slcp = max([float(x[1]) for x in co_slcp['location']['coordinates'][0]])
    if min_pre_slcp < min_co_slcp:
        overlap = max_pre_slcp - min_co_slcp
    else:
        overlap = max_co_slcp - min_pre_slcp
    length = max_co_slcp - min_co_slcp
    #print('length is {} and mins are: {} {}'.format(length, min_pre_slcp, min_co_slcp))
    return old_div(overlap, length)


def get_start_end_datetimes(slcp_obj):
    '''
    gets the start and end datetimes from the slcp metadata dict
    '''
    start = parser.parse(slcp_obj['_source']['starttime']).replace(tzinfo=pytz.utc)
    end = parser.parse(slcp_obj['_source']['endtime']).replace(tzinfo=pytz.utc)
    return start, end

def get_url(slcp_obj):
    '''
    gets the s3 url for the slcp
    '''
    url_list = slcp_obj['_source']['urls']
    return [x for x in url_list if x.startswith('s3')][0]

def submit_cod_job(url_pair, aoi_name, dataset_tag, project, queue, priority, az_lk=None, rn_lk=None):
    '''
    Submits job for COD creation
    '''
    # inherit params from current job if not specified
    ctx = load_context()
    jobjson = load_job_json()
    if dataset_tag is None:
        dataset_tag = ctx['dataset_tag']
    if project is None:
        project = ctx['project']
    if priority is None:
        priority = ctx['job_priority']
    if queue is None:
        queue = walk(jobjson, 'job_queue')
    job_tag = 'cod_{}'.format(aoi_name)
    job_version = jobjson['params']['container_specification']['version']
    url1 = url_pair[0]
    url2 = url_pair[1]
    job_params = [{'name': 'dataset_tag', 'from': 'value', 'value': dataset_tag},
                  {'name': 'project', 'from': 'value', 'value': project}, 
                  {'name': 'url1', 'from': 'value', 'value': url1},
                  {'name': 'url2', 'from': 'value', 'value': url2},
                  {'name': 'overriding_azimuth_looks', 'from': 'value', 'value': az_lk},
                  {'name': 'overriding_range_looks', 'from': 'value', 'value': rn_lk}
                  ]

    job_name = 'slcp2cod_{}_{}_{}'.format(aoi_name, os.path.basename(url1), os.path.basename(url2))
    if len(job_name) > 200:
        job_name = 'slcp2cod_{}_{}'.format(aoi_name, hashlib.sha224(job_name).hexdigest()) #TEMP FIX
    job_spec = 'job-slcp2cod:{}'.format(job_version)
    dedup = True
    submit_job(job_name, job_spec, job_params, queue, priority=priority, dedup=dedup)

def submit_job(job_name, job_spec, params, queue, priority=5, dedup=True):
    '''submits job through hysds wiring'''
    rule = {
        "rule_name": job_spec,
        "queue": queue,
        "priority": priority,
        "kwargs":'{}'
    }
    submit_mozart_job({}, rule,
                hysdsio={"id": "internal-temporary-wiring",
                         "params": params,
                         "job-specification": job_spec},
                job_name=job_name, enable_dedup=dedup)

def get_current_job_version():
    '''pulls the current job version from context'''
    ctx = load_context()
    return ctx['container_specification']['version']
    
def get_component_es_ip(component):
    '''
    Determines the components elasticsearch ip address
    @param component: string defining the endpoint. mozart,figaro,grq
    '''
    app = Celery('hysds')
    app.config_from_object('celeryconfig')
    #app.start()
    component = component.lower()
    if component == "mozart" or component == "figaro":
        es_url = app.conf["JOBS_ES_URL"]
        es_index = app.conf["STATUS_ALIAS"]
        facetview_url = app.conf["MOZART_URL"]
    elif component == "tosca" or component == "grq":
        es_url = app.conf["GRQ_ES_URL"]
        es_index = app.conf["DATASET_ALIAS"]
        facetview_url = app.conf["GRQ_URL"]
    else:
       raise NotImplementedError('Have not implemented callers for endpoint IP')
    return es_url

def search(endpoint=None, params=None, index=None, routing=None):
    '''
    Runs a search query over the given elasticsearch endpoint
    ''' 
    #get the endpoint ip
    url = get_component_es_ip(endpoint)
    if index:
        url += '/{0}'.format(index)
    #build the url
    url += '/_search'
    if routing:
        url += "?routing={0}".format(routing)
    #conduct the query
    response = es_get(url, params)
    return json.loads(response.text, encoding='ascii')

def get(endpoint=None, query=None, params=None):
    '''
    Runs a generic ES GET over the elasticsearch endpoint
    '''
    #get the endpoint ip
    url = get_component_es_ip(endpoint)
    url += '/' + query
    response = es_get(url, params)
    return json.loads(response.text, encoding='ascii')

def es_get(url, params):
    '''
    ES GET request
    '''
    try:
        #print('url: {0}'.format(url))
        #print('params: {0}'.format(params))
        response = requests.post(url, data=json.dumps(params))
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(err)
        sys.exit(1)
    return response

def argparser():
    '''
    Construct a parser to parse arguments
    @return argparse parser
    '''
    parse = argparse.ArgumentParser(description="Query ES and get SLCP pairs")
    parse.add_argument("slcp_version", help="version of SLCP")
    parse.add_argument("aoi_name", help="name of aoi")
    parse.add_argument("--dataset_tag", required=False, help="dataset tag", dest="dataset_tag", default=None)
    parse.add_argument("--project", required=False, help="project", dest="project", default=None)
    parse.add_argument("--queue", required=False, help="job queue", dest="queue", default=None)
    parse.add_argument("--priority", required=False, help="job priority", dest="priority", default=None)
    return parse

if __name__ == '__main__':
    args = argparser().parse_args()
    main(args.slcp_version, args.aoi_name, dataset_tag=args.dataset_tag, project=args.project, queue=args.queue, priority=args.priority)
