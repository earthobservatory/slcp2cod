#!/bin/bash
set -x
set -e
# Let date1, date2, date3 be in chronogical order, with event time between date2 and date3.
# Then date2-date1 becomes the pre-event pair (dir1), and date2-date3 becomes the co-event pair (dir2)
#dir1=/u/hm/Dominica/proc/S1-SLCP_RM_M1S1_TN054_20170327T095857-20170315T095830_s1-poeorb-1c62-v1.1.3-urgent_response
#dir2=/u/hm/Dominica/proc/S1-SLCP_RM_M1S2_TN054_20170327T095830-20170923T095920_s1-resorb-ddee-v1.1.3-urgent_response
dir1=$1
dir2=$2
outdir=$3
rlooks=$4
azlooks=$5

bdir1=$(basename ${dir1})
#i=1   # subswath (1, 2, or 3)
#get subswath from input filename
i=$(grep -o "[1-3]" <<< $(grep -o "_s[1-3]-" <<< ${bdir1}))

echo "Processing subswath ${i}"
dirm=${dir1}/master/IW${i}        # master directory
dirg=${dir1}/geom_master/IW${i}   # master geometry directory
dirs1=${dir1}/fine_coreg/IW${i}   # slave 1 directory
dirs2=${dir2}/fine_coreg/IW${i}   # slave 2 directory

mkdir -p ${outdir}
cd ${outdir}

#get range/azimuth looks
#nm=$(basename ${dir1})
#metf=${dir1}/${nm}.met.json
#rlooks=$(cat ${metf} | grep -Po '(?<="range_looks": )(.*?)(?=,)')
#azlooks=$(cat ${metf} | grep -Po '(?<="azimuth_looks": )(.*?)(?=,)')
# range looks dependent on subswath
#azlooks=2
#if [ "${i}" -eq "1" ]; then
#    rlooks=7 #subswath 1
#elif [ "${i}" -eq "2" ]; then
#    rlooks=8 #subswath 2
#else
#    rlooks=9 #subswath 3
#fi

script_dir=`dirname ${0}`
${script_dir}/burst_coherence_diff.py -mdir ${dirm} -sdir ${dirs1} -sdir2 ${dirs2} -gdir ${dirg} -rlks ${rlooks} -alks ${azlooks} -ssize 1.0 || true
cd ..
