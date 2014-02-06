#!/bin/bash

set -e

source /home/tyler/site/bin/environment.sh

if [ -z "$SITE_VERSION" ]; then
    echo "stop! SITE_VERSION is not set"
    exit 1
fi


SITE_NAME="researchcompendia"
VIRTUALENV=/home/tyler/venvs/$SITE_VERSION
SITE_ROOT=/home/tyler/site
DJANGODIR=${SITE_ROOT}/tyler/companionpages 
PORT=8000
BIND_IP=127.0.0.1:$PORT
USER=`whoami`
GROUP=tyler
NUM_WORKERS=3
LOG_LEVEL=debug
DJANGO_WSGI_MODULE=companionpages.wsgi

export DJANGO_SETTINGS_MODULE=companionpages.settings
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

echo "Starting $SITE_NAME version $SITE_VERSION as $USER using $VIRTUALENV"

cd $DJANGODIR

# Start your Django Unicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
exec ${VIRTUALENV}/bin/gunicorn ${DJANGO_WSGI_MODULE}:application \
  --name $SITE_NAME \
  --workers $NUM_WORKERS \
  --user=$USER \
  --group=$GROUP \
  --log-level=$LOG_LEVEL \
  --bind $BIND_IP
