#!/bin/bash

#set -x
mkdir -p $1/archive

today=$(date --date="-11 days" '+%s')
for i in $1/*; do
  d=$(basename $i)
  date=$(date --date "$d" '+%s')
  if [ $? = 0 ]; then
    if [ $date -le $today ]; then
      tar zcvf $1/archive/$d.tgz $i
      rm -Rf $i
    fi
  fi
done

set -x

rm -f $1/latest
latest=$(ls -d1 $1/????-??-?? | sort -r | head -1)
latest=$(basename $latest)/$(ls -1 ${latest})
ln -s $latest $1/latest

#rsync -avz html/ hazel.rocq.inria.fr:web/public_html/tmp/html/