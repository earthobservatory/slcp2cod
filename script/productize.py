#!/usr/bin/env python

'''
Takes input COD product path and builds a met.json and dataset.json
'''

from __future__ import print_function
import os
import json
import re
import argparse
import datetime
from shapely.geometry import Polygon, MultiPolygon, mapping
from shapely.ops import cascaded_union
from dateutil.parser import parse as dtparse

def main(prod_dir, fn1, fn2):
    #exit if there are no products
    if len(os.listdir(prod_dir)) == 0:
        print('Found no products available for publish in workdir: {}'.format(prod_dir))
        raise Exception('No COD products were generated.')
    base = os.path.basename(prod_dir)
    met = create_met(base, fn1, fn2)
    dataset = {}
    dataset_path = os.path.join(prod_dir, '{0}.dataset.json'.format(base))
    met_path = os.path.join(prod_dir, '{0}.met.json'.format(base))
    #get vars
    dataset['version'] = 'v1.0'
    #try:
    dataset['location'] = get_location(prod_dir)
    #except:
    #    print('failed generating bounds for COD')
    print('extent of COD product: {}'.format(dataset['location']))
    dataset['dataset'] = 'S1-COD'
    dataset['label'] = base
    #parse starttime/endtime from name
    dataset.update({'starttime':met['starttime'], 'endtime':met['endtime']})

    #parse info from context
    try:
        context = load_context()
        dataset['dataset_tag'] = context['dataset_tag']
        dataset['project'] = context['project']
    except:
        pass
    #write met and datasets
    with open(dataset_path, 'w') as outf:
        json.dump(dataset, outf)
    with open(met_path, 'w') as outf:
        json.dump(met, outf)

def load_context():
    with open('_context.json') as data_file:
        data = json.load(data_file)
        return data

def parse_start_end_times(base):
    times = {}
    reg = 'S1-COD_M([0-9S]*)_TN([0-9]*)_F(.*?)_S([0-9])_([0-9T]*)-([0-9T]*)-([0-9T]*)'
    match = re.search(reg, base)
    frame = match.group(1)
    track = match.group(2)
    slcpframe = match.group(3)
    subswath = match.group(4)
    start = dtparse(match.group(5)).strftime('%Y-%m-%dT%H:%M:%S')
    mid = dtparse(match.group(6)).strftime('%Y-%m-%dT%H:%M:%S')
    end = dtparse(match.group(7)).strftime('%Y-%m-%dT%H:%M:%S')
    times['starttime'] = start
    times['endtime'] = end
    times['sharedtime'] = mid
    return times

def create_met(base, fn1, fn2):
    master_slcp_metfile = os.path.join(fn1, fn1 + '.met.json')
    master_slcp_met = load_json(master_slcp_metfile)
    met = {}
    met.update(parse_start_end_times(base))
    wanted_slcp_keys = ['trackNumber','frameID', 'swath', 'direction', 'lookDirection', 'spacecraftName']
    for key in wanted_slcp_keys:
        met.update({key: master_slcp_met.get(key)})

    met['master_slcp'] = os.path.basename(fn1)
    met['slave_slcp'] = os.path.basename(fn2)
    return met

def get_vrt_met(prod_dir):
    '''
    get metadata from the vrt files in the product directory
    '''
    #build list of vrt files
    vrt_path = os.path.join(prod_dir, 'extent.vrt')
    list_path = os.path.join(prod_dir, 'vrt_list.txt')
    os.popen('ls {0}/*.vrt >> {1}'.format(prod_dir, list_path))
    os.popen('gdalbuildvrt -a_srs WGS84 -input_file_list {0} {1}'.format(list_path, vrt_path))
    met_string = os.popen('gdalinfo -json %s' % vrt_path).read()
    met = json.loads(met_string)
    print('vrt_metadata:{0}'.format(met))
    return met

def parse_corners(met):
    '''
    parses the corner points from the metadata and outputs them in geojson format
    '''
    smet = met['cornerCoordinates']
    ul = smet['upperLeft']
    ur = smet['upperRight']
    lr = smet['lowerRight']
    ll = smet['lowerLeft']
    coordinates = [ul, ur, lr, ll, ul]
    location = {'type' : 'polygon', 'coordinates' : [coordinates]}
    return location

def get_location(prod_dir):
    '''attempt to get the location from the SLCP products. Pulls the footprint from the metadata, then
    finds the intersect and returns the geojson'''
    work_dir = os.path.dirname(os.path.abspath(prod_dir))
    dirlist = os.listdir(work_dir)
    dirlist = [dirc for dirc in dirlist if os.path.isdir(dirc)] # ensure they are only folders
    slcpdirs = [dirc for dirc in dirlist if re.match(r'(S1-SLCP).*', dirc)]
    polygons = []
    for slcpdir in slcpdirs:
        filelist = os.listdir(slcpdir)
        filelist = [fle for fle in filelist if os.path.isfile(os.path.join(slcpdir, fle))]
        metfile = [dirc for dirc in filelist if re.match(r'(S1-SLCP).*(.dataset.json)', dirc)]
        for metf in metfile:
            dset = load_json(os.path.join(slcpdir, metf))
            if 'location' in dset.keys() and 'coordinates' in dset['location'].keys():
                shape_extent = Polygon(dset['location']['coordinates'][0])
                polygons.append(shape_extent)
    multi = MultiPolygon(polygons)
    return mapping(cascaded_union(multi))

def load_json(file_path):
    '''load the file path into a dict and return the dict'''
    with open(file_path, 'r') as json_data:
        json_dict = json.load(json_data)
        json_data.close()
    return json_dict

def parser():
    '''
    Construct a parser to parse arguments
    @return argparse parser
    '''
    parse = argparse.ArgumentParser(description="Generate output COD met and dataset json")
    parse.add_argument("slcp_fn1", help="master SLCP path")
    parse.add_argument("slcp_fn2", help="slave SLCP path")
    parse.add_argument("prod_dir", help="COD product directory path")

    return parse

if __name__ == '__main__':
    args = parser().parse_args()
    main(args.prod_dir, args.slcp_fn1, args.slcp_fn2)
