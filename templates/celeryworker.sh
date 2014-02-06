#!/bin/bash

set -e
source /home/tyler/site/bin/environment.sh
if [ -z "$SITE_VERSION" ]; then
    echo "stop! SITE_VERSION is not set"
    exit 1
fi
VIRTUALENV=/home/tyler/venvs/$SITE_VERSION
SITE_ROOT=/home/tyler/site
DJANGODIR=${SITE_ROOT}/tyler/companionpages 
USER=`whoami`
LOG_LEVEL=debug
export DJANGO_SETTINGS_MODULE=companionpages.settings
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

echo "Starting celery worker as $USER using $VIRTUALENV"

cd $DJANGODIR

exec ${VIRTUALENV}/bin/celery -A companionpages worker --loglevel=$LOG_LEVEL
