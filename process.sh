#!/bin/sh
out=$2
tmp=$1.tmp
if [ -e $tmp ]; then
    echo "'$tmp' exists. Aborting."
    exit
fi
if [ -z "$out"]; then 
    out=$1.processed;
fi
./vcard2to3.py --remove '.*@chat\.facebook\.com' --remove_card 'FN:New contact' --remove_dollar --prune_empty $1 $tmp
if [ $? -ne 0 ]; then
    exit
fi
./vcard_sort.py $tmp $out
if [ $? -ne 0 ]; then
    exit
fi
rm $tmp
