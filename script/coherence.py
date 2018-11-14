#!/usr/bin/env python3

import argparse
from xml.etree.ElementTree import ElementTree

import isce
import isceobj
import operator

from iscesys.ImageUtil.ImageUtil import ImageUtil as IU
from mroipac.correlation.correlation import Correlation

#logger = logging.getLogger('isce.insar.runCoherence')

## mapping from algorithm method to Correlation instance method name
CORRELATION_METHOD = {
    'phase_gradient' : operator.methodcaller('calculateEffectiveCorrelation'),
    'cchz_wave' : operator.methodcaller('calculateCorrelation')
    }

def getWidth(xmlfile):
    xmlfp = None
    try:
        xmlfp = open(xmlfile,'r')
        print('reading file width from: {0}'.format(xmlfile))
        xmlx = ElementTree(file=xmlfp).getroot()
        width = int(xmlx.find("component[@name='Coordinate1']/property[@name='size']/value").text)
        print("file width: {0}".format(width))
    except (IOError, OSError) as strerr:
        print("IOError: %s" % strerr)
        return []
    finally:
        if xmlfp is not None:
            xmlfp.close()
    return width

def coherence(inps, method="phase_gradient"):
                          
    #logger.info("Calculating Coherence")

    #get width from the header file of input interferogram
    width = getWidth(inps.intf + '.xml')

    # Initialize the amplitude
    ampImage = isceobj.createAmpImage()
    ampImage.setFilename(inps.amp)
    ampImage.setWidth(width)
    ampImage.setAccessMode('read')
    ampImage.createImage()
    #ampImage = self.insar.getResampOnlyAmp().copy(access_mode='read')
    
    # Initialize the flattened inteferogram
    intImage = isceobj.createIntImage()
    intImage.setFilename(inps.intf)
    intImage.setWidth(width)
    intImage.setAccessMode('read')
    intImage.createImage()

    # Create the coherence image
    #there is no coherence image in the isceobj/Image
    cohImage = isceobj.createOffsetImage()
    cohImage.setFilename(inps.cor)
    cohImage.setWidth(width)
    cohImage.setAccessMode('write')
    cohImage.createImage()

    cor = Correlation()
    cor.configure()
    cor.wireInputPort(name='interferogram', object=intImage)
    cor.wireInputPort(name='amplitude', object=ampImage)
    cor.wireOutputPort(name='correlation', object=cohImage)
    cor.windowSize = inps.winsize

    cohImage.finalizeImage()
    intImage.finalizeImage()
    ampImage.finalizeImage()

    try:
        CORRELATION_METHOD[method](cor)
    except KeyError:
        print("Unrecognized correlation method")
        sys.exit(1)
        pass
    return None



def cmdLineParse():
    '''
    Command line parser.
    '''

    parser = argparse.ArgumentParser( description='estimate interferogram coherence')

    parser.add_argument('-i','--intf', dest='intf', type=str,
            required=True, help='input interferogram')
    parser.add_argument('-a','--amp', dest='amp', type=str,
            required=True, help='input amplitude image')
    parser.add_argument('-c','--cor', dest='cor', type=str,
            required=True, help='coherence file')
    parser.add_argument('-m','--method', dest='method', type=int,
            default=0, help='coherence calculation method. 0: cchz_wave; 1: phase_gradient. DEFAULT: 0')
    parser.add_argument('-w','--winsize', dest='winsize', type=int,
            default=5, help='window size when calculating coherence')

    return parser.parse_args()

if __name__ == '__main__':
    '''
    Main driver.
    '''

    inps = cmdLineParse()

    if inps.method == 0:
        method = 'cchz_wave'
        print("\ncalculating coherence using cchz_wave\n")
    else:
        method = 'phase_gradient'
        print("\ncalculating coherence using phase_gradient\n")
    
    coherence(inps, method)

#./coherence.py -i diff_20130927-20141211_16rlks_16alks.int -a 20130927-20141211_16rlks_16alks.amp -c 20130927-20141211_16rlks_16alks.cor 














