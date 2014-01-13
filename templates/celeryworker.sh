#!/bin/bash

set -e
if [ -z "$SITE_VERSION" ]; then
    echo "stop! SITE_VERSION is not set"
    exit 1
fi
VIRTUALENV=/home/tyler/venvs/$SITE_VERSION
SITE_ROOT=/home/tyler/site
SITE_ENVIRONMENT=${SITE_ROOT}/env
DJANGODIR=${SITE_ROOT}/tyler/companionpages 
USER=`whoami`
LOG_LEVEL=debug
export DJANGO_SETTINGS_MODULE=companionpages.settings
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

echo "Starting celery worker as $USER using $SITE_ENVIRONMENT and $VIRTUALENV"
source ${VIRTUALENV}/bin/activate

cd $DJANGODIR

exec envdir $SITE_ENVIRONMENT celery -A companionpages worker --loglevel=$LOG_LEVEL
