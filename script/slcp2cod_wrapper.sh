#!/bin/bash
set -x
set -e

url1=$(python -c 'import json; print(json.load(open("_context.json"))["localize_urls"][0]["url"])')
url2=$(python -c 'import json; print(json.load(open("_context.json"))["localize_urls"][1]["url"])')
fn1_base=$(basename ${url1})
fn2_base=$(basename ${url2})

fn1=$(pwd)/${fn1_base}
fn2=$(pwd)/${fn2_base}

#determine outproduct name
#fout=$(echo ${fn1_base:0:37}${fn2_base:37:15}${fn1_base:52:50} | sed 's/S1-SLCP/S1-COD/g')
#run dir
script_dir=`dirname ${0}`
#determine out name
fout=$(${script_dir}/rename.py ${fn1_base} ${fn2_base})

#set configs
parent_dir=$(dirname ${script_dir})
source ${parent_dir}/set_env_variable.sh

#pull the first and second  dirs
#aws s3 cp ${s31} ${fn1} --recursive
#aws s3 cp ${s32} ${fn2} --recursive

#get subswath
subswath=$(grep -o "[1-3]" <<< $(grep -o "_s[1-3]-" <<< ${fn1}))

rlooks=$(${script_dir}/get_looks.py ${fn1} 'rn')
azlooks=$(${script_dir}/get_looks.py ${fn1} 'az')

#run cod script
${script_dir}/slcp2cod_S1.sh ${fn1} ${fn2} ${fout} ${rlooks} ${azlooks}

#productize
${script_dir}/productize.py ${fn1} ${fn2} ${fout} ${rlooks} ${azlooks}

#remove old dirs
rm -rf ${fn1}
rm -rf ${fn2}
