
dir0=/u/hm/ARIAtest/data/S1-REG_SLC_PAIR_STCM1S1_TN115_20150821T141548-20150914T141616_s1-poeorb-v1.1
i=1

dirm=${dir0}/master/IW${i}
dirf=${dir0}/fine_coreg/IW${i}
dirg=${dir0}/geom_master/IW${i}

mkdir s${i}
cd s${i}

log_ratio.py -mdir ${dirm} -sdir ${dirf} -gdir ${dirg} -rlks 7 -alks 2

