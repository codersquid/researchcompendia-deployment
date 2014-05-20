#!/bin/bash

# @hourly (/home/tyler/site/bin/update_index.sh >> /home/tyler/site/logs/cron_update_index.log 2>&1)

set -e
source /home/tyler/site/bin/environment.sh
if [ -z "$SITE_VERSION" ]; then
    echo "stop! SITE_VERSION is not set"
    exit 1
fi
VIRTUALENV=/home/tyler/venvs/$SITE_VERSION
SITE_ROOT=/home/tyler/site
SITE_ENVIRONMENT=${SITE_ROOT}/env
DJANGODIR=${SITE_ROOT}/tyler/companionpages 
export DJANGO_SETTINGS_MODULE=companionpages.settings
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

echo "Starting update_index using $SITE_ENVIRONMENT and $VIRTUALENV"
source ${VIRTUALENV}/bin/activate

cd $DJANGODIR

./manage.py update_index
