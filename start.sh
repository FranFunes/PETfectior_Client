#!/bin/bash
mount -t cifs $SHARED_PATH $SHARED_MOUNT_POINT -o username=$NAS_USERNAME,password=$NAS_PASSWORD
source envPETfectiorClient/bin/activate
while true; do
    echo Waiting for database...
    flask db upgrade > /dev/null 2>&1
    if [[ "$?" == "0" ]]; then
        break
    fi
    echo Upgrade command failed, retrying in 5 secs...
    sleep 5
done
flask run