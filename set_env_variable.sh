#!/bin/bash
#set environment variables here
NEWHOME="/home/ops/verdi/ops"
export INSAR_ZERODOP_SCR=$NEWHOME/slcp2cod/script
export INSAR_ZERODOP_BIN=$NEWHOME/slcp2cod/src
export PATH=$INSAR_ZERODOP_SCR:$INSAR_ZERODOP_BIN:$PATH 

export PYTHONPATH=/usr/local/isce:$PYTHONPATH
export ISCE_HOME=/usr/local/isce/isce
export PATH=$ISCE_HOME/applications:$ISCE_HOME/bin:/usr/local/gdal/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/gdal/lib:$LD_LIBRARY_PATH
export GDAL_DATA=/usr/local/gdal/share/gdal
