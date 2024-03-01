#!/bin/bash

BASEDIR=$(dirname "$0")
source $BASEDIR/auto_detect_env.sh

# stop services created by runsv and propagate SIGTERM to child jobs
sv_stop() {
    echo "$(date -uIns) - Stopping all runsv services"
    for s in $(ls -d /var/runit/*); do
        sv stop $s
    done
}
 
# register SIGTERM handler
trap sv_stop SIGTERM

# start services in background and wait all child jobs
runsvdir /var/runit &
wait
