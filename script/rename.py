#!/usr/bin/env python

'''
Takes input SLCP filename and outputs the COD product name
'''

from __future__ import print_function
import os
import re
import json
import argparse
import datetime
from dateutil.parser import parse as dtparse

def main(fn1, fn2):
    reg = '_M([0-9S]*)_TN([0-9]*)_([0-9]+T[0-9]*)-([0-9]+T[0-9]*)_s([0-9]).*'
    match = re.search(reg, fn1)
    frame = match.group(1)
    track = match.group(2)
    #print('track: {0}'.format(track))
    t1 = match.group(3)
    t2 = match.group(4)
    match2 = re.search(reg, fn2)
    t3 = match2.group(3)
    t4 = match2.group(4)
    subswath = match.group(5)
    #get the duplicate
    tlist = [t1,t2,t3,t4]
    dtlist = [dtparse(x) for x in tlist]
    dt_sorted = sorted(dtlist)
    dt_str = [x.strftime('%Y%m%dT%H%M%S') for x in dt_sorted]
    start = dt_str[0]
    shared_time = dt_str[1]
    end = dt_str[3]
    dtag = 'urgent_response'
    version = 'v1.0'
    ctx = load_context()
    if 'dataset_tag' in ctx.keys():
        dtag = ctx['dataset_tag']
    if 'version' in ctx.keys():
        version = ctx['version']
    metfile = os.path.join(fn1, fn1 + '.met.json')
    met = load_file(metfile)
    frameid = met['frameID']
    dsfile = os.path.join(fn1, fn1 + '.dataset.json')
    ds = load_file(dsfile)
    slcp_version = ds['version']
    out = 'S1-COD_M{0}_TN{1}_F{2}_S{3}_{4}-{5}-{6}-{7}-{8}'.format(frame,track,frameid,subswath,start,shared_time,end,slcp_version,dtag)
    print(out)

def load_context():
    with open('_context.json') as data_file:
        data = json.load(data_file)
        return data

def load_file(fname):
    with open(fname) as data_file:
        data = json.load(data_file)
        return data

def within_list(dtlist, dt):
    '''
    Returns True if dt is within an hour of any other datetime in the list
    '''
    for dt2 in dtlist:
        if dt2 != dt and within_an_hour(dt,dt2):
            return True
    return False
            

def within_an_hour(dt1,dt2):
    '''
    returns True if the two datetimes are within an hour of each other
    '''
    margin = datetime.timedelta(hours = 1)
    #make dt1 first
    if dt1 > dt2:
        dt1,dt2 = dt2,dt1
    if (dt2 - dt1) < margin:
        return True
    return False


def parser():
    '''
    Construct a parser to parse arguments
    @return argparse parser
    '''
    parse = argparse.ArgumentParser(description="Generate output COD filename")
    parse.add_argument("file1", help="file1")
    parse.add_argument("file2",  help="file2")
    return parse

if __name__ == '__main__':
    args = parser().parse_args()
    main(args.file1, args.file2)
