#!/bin/bash

BASEDIR=$(dirname "$0")
source $BASEDIR/auto_detect_env.sh

# start services in background and wait all child jobs
runsvdir /var/runit &
wait
