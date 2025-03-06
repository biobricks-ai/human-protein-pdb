#!/usr/bin/env bash

# Script to download files

# Get local path
localpath=$(pwd)
srcpath=$(pwd)/src
echo "Local path: $localpath"

FILE=$srcpath/pdb_ids.txt
#FILE=$srcpath/missing_pdb_ids.txt
BATCH_SCRIPT=$srcpath/batch_download.sh

# Ensure batch_download.sh is present
if [ ! -f "$BATCH_SCRIPT" ]; then
    echo "Error: batch_download.sh not found. Please place it in the src directory." >&2
    exit 1
fi

# Ensure pdb_ids.txt exists
if [ ! -f "$FILE" ]; then
    echo "Error: $FILE not found. Ensure it is generated before running this script." >&2
    exit 1
fi

# Create the download directory
export downloadpath="$localpath/download"
echo "Download path: $downloadpath"
mkdir -p "$downloadpath"
cd $downloadpath;

# Run batch_download.sh with the specified file
chmod +x $BATCH_SCRIPT
#$BATCH_SCRIPT -f "$FILE" -p 2>&1 | tee download.log
#python $srcpath/batch_download.py -f "$FILE" -p --rsync 2>&1 | tee download.log
python $srcpath/batch_download.py -f "$FILE" -p 2>&1 | tee download.log

echo "Download done."
