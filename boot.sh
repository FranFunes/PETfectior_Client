#!/bin/bash
while true; do
    echo Mounting $SHARED_PATH on $SHARED_MOUNT_POINT...
    mount -t cifs $SHARED_PATH $SHARED_MOUNT_POINT -o username=$NAS_USERNAME,password=$NAS_PASSWORD
    if [[ "$?" == "0" ]]; then
        break
    fi
    echo mount command failed, retrying in 5 secs...
    sleep 5
done

source envPETfectiorClient/bin/activate

while true; do
    echo Waiting for database...
    flask db upgrade
    if [[ "$?" == "0" ]]; then
        break
    fi
    echo Upgrade command failed, retrying in 5 secs...
    sleep 5
done
exec gunicorn -b :$FLASK_RUN_PORT --access-logfile - --error-logfile - petfectior_client:application