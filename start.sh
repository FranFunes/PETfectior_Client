#!/bin/bash
mount -t cifs $SHARED_PATH $SHARED_MOUNT_POINT -o username=$NAS_USERNAME,password=$NAS_PASSWORD
flask run