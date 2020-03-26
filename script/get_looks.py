#!/usr/bin/env python

'''
Determine looks for COD processing
'''
import json
import argparse
import os


def main(master_slcp_dir, option):
    ctx = load_json('_context.json')
    ctx_key = "overriding_azimuth_looks" if option == "az" else "overriding_range_looks"
    met_key = "azimuth_looks" if option == "az" else "range_looks"
    looks = ctx[ctx_key]
    if looks:
        print(looks)
    else:
        slcp_met = load_json(os.path.join(
            master_slcp_dir, os.path.basename(master_slcp_dir) + '.met.json'))
        print(slcp_met[met_key])


def load_json(file):
    with open(file) as data_file:
        data = json.load(data_file)
        data_file.close()
        return data


def parser():
    '''
    Construct a parser to parse arguments
    @return argparse parser
    '''
    parse = argparse.ArgumentParser(
        description="Determine azimuth and range looks for COD processing")
    parse.add_argument("master_slcp_dir", help="master SLCP directory")
    parse.add_argument(
        "look_dir", help="Look direction. Either 'az' for azimuth or 'rn' for range")

    return parse


if __name__ == '__main__':
    args = parser().parse_args()
    main(args.master_slcp_dir, args.look_dir)
