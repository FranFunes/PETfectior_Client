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

# Create the admin user if it doesn't exist
python init_db.py
exec gunicorn -b :$FLASK_RUN_PORT --access-logfile $LOGGING_FILEPATH/gunicorn_access.log --error-logfile $LOGGING_FILEPATH/gunicorn_errors.log petfectior_client:application