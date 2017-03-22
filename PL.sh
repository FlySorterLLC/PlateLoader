#!/bin/bash

DATE=`date +%Y%m%d-%H%M%S`
DIR=`dirname "${BASH_SOURCE[0]}"`
cd "$DIR"
python wxApp.py > "logs/log-$DATE.txt"
