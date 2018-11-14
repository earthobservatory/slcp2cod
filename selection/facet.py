#!/usr/bin/env python
'''
Submits ElasticSearch query, builds list of SLCP pairs
'''

from __future__ import print_function
import sys
import os
import json
import logging
import requests
import argparse
import itertools
from hysds.celery import app
from dateutil import parser
from datetime import timedelta

from celery import Celery
import submit_job


def main():
    #load eveything from context.json
    ctx = load_context()
    dataset_tag = ctx['dataset_tag']
    project = ctx['project']
    queue = 'aria-job_worker-large'
    query_str = ctx['query']
    query = json.loads(query_str)

    results = search(endpoint='grq', params=query)
    #print('slcp results: {0}'.format(results))
    r_dict = results
    url_pairs = determine_valid_pairs(r_dict)
    if len(url_pairs) > 0:
        print('submitting COD jobs...')
    else:
        print('no COD jobs to submit.')
    for pair in url_pairs:
        submit_cod_job(pair, dataset_tag, project, queue)

def load_context():
    with open('_context.json') as data_file:
        data = json.load(data_file)
        return data

def determine_valid_pairs(slcp_dict):
    '''
    Determines which SLCP pairs are valid co-event pairs
    returns a list of s3 url pairs that match
    '''
    slcp_list = []
    for slcp in slcp_dict['hits']['hits']:
        #print('slcp: {0}'.format(slcp))
        start,end = get_start_end_datetimes(slcp)
        url = get_url(slcp)
        track_num = slcp['_source']['metadata']['trackNumber']
        orbit_num = slcp['_source']['metadata']['orbitNumber']
        frame_id = slcp['_source']['metadata']['frameID']
        slcp_list.append({'start': start, 'end': end, 'url': url, 'track': track_num, 'orbit': orbit_num[0], 'frame': frame_id})
        print('starttime: {0}, endtime: {1}, type: {2}'.format(start,end, 'pre-event'))
    print('found {0}  slcps'.format(len(slcp_list)))
    #determine pairs that share start & end
    possible_pairs = list(itertools.permutations(slcp_list, 2))
    valid_pairs = []
    for pair in possible_pairs:
        pre_slcp = pair[0]
        co_slcp = pair[1]
        #ensure pre_slcp is prior scene
        if pre_slcp['start'] > co_slcp['start']:
            continue
        if pre_slcp['end'] > co_slcp['end']:
            continue
        print('checking if {0} matches {1} '.format(pre_slcp['end'].strftime('%Y-%m-%dT%H:%M:%S'),co_slcp['start'].strftime('%Y-%m-%dT%H:%M:%S')))
        if (co_slcp['track'] == pre_slcp['track'] and co_slcp['orbit'] == pre_slcp['orbit'] and co_slcp['frame'] == pre_slcp['frame']):
            print('found valid pairs for track: {0}, orbit: {1}, and frame: {2}'.format(co_slcp['track'], co_slcp['orbit'], co_slcp['frame']))
            valid_pairs.append( (pre_slcp['url'], co_slcp['url']) )
    print('found {0} valid slcp pairs for cod processing'.format(len(valid_pairs)))
    return valid_pairs

def get_start_end_datetimes(slcp_obj):
    '''
    gets the start and end datetimes from the slcp metadata dict
    '''
    start = parser.parse(slcp_obj['_source']['starttime'])
    end = parser.parse(slcp_obj['_source']['endtime'])
    return start,end

def get_url(slcp_obj):
    '''
    gets the s3 url for the slcp
    '''
    url_list = slcp_obj['_source']['urls']
    return filter(lambda x: x.startswith('s3'), url_list)[0]



def submit_cod_job(url_pair, dataset_tag, project, queue):
    '''
    Submits job for COD creation
    '''
    url1 = url_pair[0]
    url2 = url_pair[1]
    path1 = url1.split("/")[-1]
    path2 = url2.split("/")[-1]
    job_params = {'dataset_tag': dataset_tag, 'project': project, 'localize_url1': url1, 'path1': path1, 'localize_url2': url2, 'path2': path2}
    mozart_url = '{0}{1}'.format(get_component_es_ip('mozart').rstrip(':9200').replace('http:', 'https:'), '/mozart/api/v0.2/job/submit')
    #print(mozart_url)
    #queue = 'aria-job_worker-large'
    job_name = 'job-slcp2cod'
    release = 'master'
    priority = 5
    dedup = True
    tags = 'cod,{0}'.format(dataset_tag)
    submit_job.main(queue=queue, mozart_url=mozart_url, job_name=job_name, release=release, priority=priority,
                    dedup=dedup, tags=tags, params=json.dumps(job_params))

def get_component_es_ip(component):
    '''
    Determines the components elasticsearch ip address
    @param component: string defining the endpoint. mozart,figaro,grq
    '''
    app = Celery('hysds')
    app.config_from_object('celeryconfig')
    #app.start()
    component = component.lower()
    if component=="mozart" or component=="figaro":
        es_url = app.conf["JOBS_ES_URL"]
        es_index = app.conf["STATUS_ALIAS"]
        facetview_url = app.conf["MOZART_URL"]
    elif component=="tosca" or component=="grq":
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
    url +='/_search'
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


if __name__ == '__main__':
    main()
