#!/usr/bin/env python3



from __future__ import division
from builtins import range
from past.utils import old_div
import os
import sys
import glob
import shutil
import ntpath
import pickle
import datetime
import argparse
import numpy as np
import numpy.matlib
from xml.etree.ElementTree import ElementTree
import traceback
import isce
import isceobj
from imageMath import IML



def runCmd(cmd):
    
    print("{}".format(cmd))
    status = os.system(cmd)
    if status != 0:
        raise Exception('error when running:\n{}\n'.format(cmd))

def getWidth(xmlfile):
    xmlfp = None
    try:
        xmlfp = open(xmlfile,'r')
        print('reading file width from: {0}'.format(xmlfile))
        xmlx = ElementTree(file=xmlfp).getroot()
        tmp = xmlx.find("component[@name='coordinate1']/property[@name='size']/value")
        if tmp == None:
            tmp = xmlx.find("component[@name='Coordinate1']/property[@name='size']/value")
        width = int(tmp.text)
        print("file width: {0}".format(width))
    except (IOError, OSError) as strerr:
        print("IOError: %s" % strerr)
        return []
    finally:
        if xmlfp is not None:
            xmlfp.close()
    return width

def getLength(xmlfile):
    xmlfp = None
    try:
        xmlfp = open(xmlfile,'r')
        print('reading file length from: {0}'.format(xmlfile))
        xmlx = ElementTree(file=xmlfp).getroot()
        tmp = xmlx.find("component[@name='coordinate2']/property[@name='size']/value")
        if tmp == None:
            tmp = xmlx.find("component[@name='Coordinate2']/property[@name='size']/value")
        length = int(tmp.text)
        print("file length: {0}".format(length))
    except (IOError, OSError) as strerr:
        print("IOError: %s" % strerr)
        return []
    finally:
        if xmlfp is not None:
            xmlfp.close()
    return length


def create_xml(fileName, width, length, fileType):
    
    if fileType == 'slc':
        image = isceobj.createSlcImage()
    elif fileType == 'int':
        image = isceobj.createIntImage()
    elif fileType == 'amp':
        image = isceobj.createAmpImage()
    elif fileType == 'rmg':
        image = isceobj.Image.createUnwImage()
    elif fileType == 'float':
        image = isceobj.createImage()
        image.setDataType('FLOAT')

    image.setFilename(fileName)
    image.setWidth(width)
    image.setLength(length)
        
    image.setAccessMode('read')
    #image.createImage()
    image.renderVRT()
    image.renderHdr()
    #image.finalizeImage()


def create_amp(width, length, master, slave, amp):
    amp_data = np.zeros((length, width*2), dtype=np.float)
    amp_data[:, 0:width*2:2] = np.absolute(master) * (np.absolute(slave)!=0)
    amp_data[:, 1:width*2:2] = np.absolute(slave) * (np.absolute(master)!=0)
    amp_data.astype(np.float32).tofile(amp)
    create_xml(amp, width, length, 'amp')


def cmdLineParse():
    '''
    Command line parser.
    '''
    parser = argparse.ArgumentParser( description='log ratio')
    parser.add_argument('-mdir', dest='mdir', type=str, required=True,
            help = 'master directory containing the bursts')
    parser.add_argument('-sdir', dest='sdir', type=str, required=True,
            help = 'slave directory containing the bursts')
    parser.add_argument('-sdir2', dest='sdir2', type=str, required=True,
            help = 'slave directory containing the bursts 2')


    parser.add_argument('-gdir', dest='gdir', type=str, required=True,
            help = 'geometric directory containing the lat/lon files ')

    parser.add_argument('-rlks',dest='rlks', type=int, default=0,
            help = 'number of range looks')
    parser.add_argument('-alks',dest='alks', type=int, default=0,
            help = 'number of azimuth looks')


    parser.add_argument('-ssize', dest='ssize', type=float, default=1.0,
            help = 'output geocoded sample size. default: 1.0 arcsec')


    return parser.parse_args()

def main():
    SCR_DIR = "$INSAR_ZERODOP_SCR"

    inps = cmdLineParse()

    mbursts = sorted(glob.glob(os.path.join(inps.mdir, 'burst_*.slc')))
    # sbursts = sorted(glob.glob(os.path.join(inps.sdir, 'burst_*.slc')))
    # sbursts2 = sorted(glob.glob(os.path.join(inps.sdir2, 'burst_*.slc')))

    nmb = len(mbursts)  # number of master bursts
    # nsb = len(sbursts) #number of slave bursts
    # nsb2 = len(sbursts2) #number of burst interferograms

    # lats = sorted(glob.glob(os.path.join(inps.gdir, 'lat_*.rdr')))
    # lons = sorted(glob.glob(os.path.join(inps.gdir, 'lon_*.rdr')))

    # if nmb != nsb:
    #    raise Exception('nmb != nsb\n')
    # if nmb != nsb2:
    #    raise Exception('nmb != nsb2\n')

    nb = nmb

    for i in range(nb):
        print('+++++++++++++++++++++++++++++++++++')
        print('processing burst {} of {}'.format(i + 1, nb))
        print('+++++++++++++++++++++++++++++++++++')

        mslc = ntpath.basename(mbursts[i])
        if os.path.isfile(os.path.join(inps.sdir, mslc)) == False or os.path.isfile(
                os.path.join(inps.sdir2, mslc)) == False:
            print('skipping this burst')
            continue

        width = getWidth(mbursts[i] + '.xml')
        length = getLength(mbursts[i] + '.xml')

        width_looked = int(old_div(width, inps.rlks))
        length_looked = int(old_div(length, inps.alks))

        master = np.fromfile(mbursts[i], dtype=np.complex64).reshape(length, width)
        slave = np.fromfile(os.path.join(inps.sdir, mslc), dtype=np.complex64).reshape(length, width)
        slave2 = np.fromfile(os.path.join(inps.sdir2, mslc), dtype=np.complex64).reshape(length, width)
        inf = master * np.conj(slave)
        inf2 = master * np.conj(slave2)

        interferogram = 'inf.int'
        inf.astype(np.complex64).tofile(interferogram)
        create_xml(interferogram, width, length, 'int')

        interferogram2 = 'inf2.int'
        inf2.astype(np.complex64).tofile(interferogram2)
        create_xml(interferogram2, width, length, 'int')

        amp = 'amp_%02d.amp' % (i + 1)
        create_amp(width, length, master, slave, amp)

        amp2 = 'amp2_%02d.amp' % (i + 1)
        create_amp(width, length, master, slave2, amp2)

        amp_looked = 'amp_%02d_%drlks_%dalks.amp' % (i + 1, inps.rlks, inps.alks)
        cmd = "{}/look.py -i {} -o {} -r {} -a {}".format(SCR_DIR,
                                                          amp,
                                                          amp_looked,
                                                          inps.rlks,
                                                          inps.alks)
        runCmd(cmd)

        amp_looked2 = 'amp2_%02d_%drlks_%dalks.amp' % (i + 1, inps.rlks, inps.alks)
        cmd = "{}/look.py -i {} -o {} -r {} -a {}".format(SCR_DIR,
                                                          amp2,
                                                          amp_looked2,
                                                          inps.rlks,
                                                          inps.alks)
        runCmd(cmd)

        interferogram_looked = 'inf_%02d_%drlks_%dalks.amp' % (i + 1, inps.rlks, inps.alks)
        cmd = "{}/look.py -i {} -o {} -r {} -a {}".format(SCR_DIR,
                                                          interferogram,
                                                          interferogram_looked,
                                                          inps.rlks,
                                                          inps.alks)
        runCmd(cmd)

        interferogram_looked2 = 'inf2_%02d_%drlks_%dalks.amp' % (i + 1, inps.rlks, inps.alks)
        cmd = "{}/look.py -i {} -o {} -r {} -a {}".format(SCR_DIR,
                                                          interferogram2,
                                                          interferogram_looked2,
                                                          inps.rlks,
                                                          inps.alks)
        runCmd(cmd)

        cor_looked = 'cor_%02d_%drlks_%dalks.cor' % (i + 1, inps.rlks, inps.alks)
        # cmd = "{}/coherence.py -i {} -a {} -c {}".format(SCR_DIR,
        #    interferogram_looked,
        #    amp_looked,
        #    cor_looked)
        cmd = "imageMath.py -e='sqrt(b_0*b_0+b_1*b_1)*(abs(a)!=0)*(b_0!=0)*(b_1!=0);abs(a)/(b_0*b_1+(b_0*b_1==0))*(abs(a)!=0)*(b_0!=0)*(b_1!=0)' --a={} --b={} -o {} -t float -s BIL".format(
            interferogram_looked,
            amp_looked,
            cor_looked)
        runCmd(cmd)

        cor_looked2 = 'cor2_%02d_%drlks_%dalks.cor' % (i + 1, inps.rlks, inps.alks)
        # cmd = "{}/coherence.py -i {} -a {} -c {}".format(SCR_DIR,
        #    interferogram_looked2,
        #    amp_looked2,
        #    cor_looked2)
        cmd = "imageMath.py -e='sqrt(b_0*b_0+b_1*b_1)*(abs(a)!=0)*(b_0!=0)*(b_1!=0);abs(a)/(b_0*b_1+(b_0*b_1==0))*(abs(a)!=0)*(b_0!=0)*(b_1!=0)' --a={} --b={} -o {} -t float -s BIL".format(
            interferogram_looked2,
            amp_looked2,
            cor_looked2)
        runCmd(cmd)

        cor_diff_looked = 'diff_cor_%02d_%drlks_%dalks.cor' % (i + 1, inps.rlks, inps.alks)
        cor_amp = (np.fromfile(cor_looked, dtype=np.float32).reshape(length_looked * 2, width_looked))[
                  0:length_looked * 2:2, :]
        cor = (np.fromfile(cor_looked, dtype=np.float32).reshape(length_looked * 2, width_looked))[
              1:length_looked * 2:2, :]
        cor2 = (np.fromfile(cor_looked2, dtype=np.float32).reshape(length_looked * 2, width_looked))[
               1:length_looked * 2:2, :]

        cor_diff = np.zeros((length_looked * 2, width_looked))
        cor_diff[0:length_looked * 2:2, :] = cor_amp * (cor_amp != 0) * (cor != 0) * (cor2 != 0)
        cor_diff[1:length_looked * 2:2, :] = (cor - cor2) * (cor_amp != 0) * (cor != 0) * (cor2 != 0)
        cor_diff.astype(np.float32).tofile(cor_diff_looked)
        create_xml(cor_diff_looked, width_looked, length_looked, 'rmg')

        lat_looked = 'lat_%02d_%drlks_%dalks.rdr' % (i + 1, inps.rlks, inps.alks)
        cmd = "{}/look.py -i {} -o {} -r {} -a {}".format(SCR_DIR,
                                                          os.path.join(inps.gdir, 'lat_%02d.rdr' % (i + 1)),
                                                          lat_looked,
                                                          inps.rlks,
                                                          inps.alks)
        runCmd(cmd)

        lon_looked = 'lon_%02d_%drlks_%dalks.rdr' % (i + 1, inps.rlks, inps.alks)
        cmd = "{}/look.py -i {} -o {} -r {} -a {}".format(SCR_DIR,
                                                          os.path.join(inps.gdir, 'lon_%02d.rdr' % (i + 1)),
                                                          lon_looked,
                                                          inps.rlks,
                                                          inps.alks)
        runCmd(cmd)

        lat_looked_data = np.fromfile(lat_looked, dtype=np.float64).reshape(length_looked, width_looked)
        lon_looked_data = np.fromfile(lon_looked, dtype=np.float64).reshape(length_looked, width_looked)

        lat_max = np.amax(lat_looked_data)
        lat_min = np.amin(lat_looked_data)
        lon_max = np.amax(lon_looked_data)
        lon_min = np.amin(lon_looked_data)
        bbox = [lat_min, lat_max, lon_min, lon_max]

        script_dir = os.path.dirname(os.path.realpath(__file__))
        cor_diff_looked_geo = 'diff_cor_%02d_%drlks_%dalks.cor.geo' % (i + 1, inps.rlks, inps.alks)
        cmd = "{}/geo_with_ll.py -input {} -output {} -lat {} -lon {} -bbox \"{}\" -ssize {} -rmethod {}".format(
            script_dir,
            cor_diff_looked,
            cor_diff_looked_geo,
            lat_looked,
            lon_looked,
            bbox,
            inps.ssize,
            1)
        runCmd(cmd)

        os.remove(interferogram)
        os.remove(interferogram2)
        os.remove(amp)
        os.remove(amp2)
        os.remove(amp_looked)
        os.remove(amp_looked2)
        os.remove(interferogram_looked)
        os.remove(interferogram_looked2)
        # os.remove(cor_looked)
        # os.remove(cor_looked2)
        # os.remove(cor_diff_looked)
        os.remove(lat_looked)
        os.remove(lon_looked)

        os.remove(interferogram + '.xml')
        os.remove(interferogram2 + '.xml')
        os.remove(amp + '.xml')
        os.remove(amp2 + '.xml')
        os.remove(amp_looked + '.xml')
        os.remove(amp_looked2 + '.xml')
        os.remove(interferogram_looked + '.xml')
        os.remove(interferogram_looked2 + '.xml')
        # os.remove(cor_looked+'.xml')
        # os.remove(cor_looked2+'.xml')
        # os.remove(cor_diff_looked+'.xml')
        os.remove(lat_looked + '.xml')
        os.remove(lon_looked + '.xml')

        os.remove(interferogram + '.vrt')
        os.remove(interferogram2 + '.vrt')
        os.remove(amp + '.vrt')
        os.remove(amp2 + '.vrt')
        os.remove(amp_looked + '.vrt')
        os.remove(amp_looked2 + '.vrt')
        os.remove(interferogram_looked + '.vrt')
        os.remove(interferogram_looked2 + '.vrt')
        # os.remove(cor_looked+'.vrt')
        # os.remove(cor_looked2+'.vrt')
        # os.remove(cor_diff_looked+'.vrt')
        os.remove(lat_looked + '.vrt')
        os.remove(lon_looked + '.vrt')


if __name__ == '__main__':
    try:
        status = main()
    except (Exception, SystemExit) as e:
        with open('_alt_error.txt', 'w') as f:
            f.write("%s\n" % str(e))
        with open('_alt_traceback.txt', 'w') as f:
            f.write("%s\n" % traceback.format_exc())
        raise
    sys.exit(status)













#sdir=/u/hm/NC/data/S1-COH_STCM3S3_TN077_20160929T231332-20161011T231433_s1-resorb-v1.0
#burst_coherence.py -mdir ${sdir}/master -sdir ${sdir}/fine_coreg -idir ${sdir}/master -gdir ${sdir}/geom_master -rlks 7 -alks 2 -ssize 1.0


