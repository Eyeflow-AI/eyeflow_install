#!/bin/bash

PURGE_DATE=`date +%Y%m%d -d "8 days ago"`
EVENT_FOLDER="/opt/eyeflow/data/event_images"

if [ -d "$EVENT_FOLDER/$PURGE_DATE" ]
then
    rm -rf "$EVENT_FOLDER/$PURGE_DATE"
fi

PURGE_DATE=`date +%Y%m%d -d "2 days ago"`
VIDEO_FOLDER="/opt/eyeflow/data/video"
if [ -d "$VIDEO_FOLDER/$PURGE_DATE" ]
then
    rm -rf "$VIDEO_FOLDER/$PURGE_DATE"
fi
