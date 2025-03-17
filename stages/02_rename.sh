#!/usr/bin/env bash

# Script to rename files from PDB ID -> UniProt ID

# Get local path
localpath=$(pwd)
srcpath=$(pwd)/src
echo "Local path: $localpath"

FILE=$srcpath/pdb_ids.txt

# Create the download directory
export downloadpath="$localpath/download"
echo "Download path: $downloadpath"
cd $downloadpath;

# Run renaming script within the download directory
python $srcpath/pdb_to_uniprot.py | tee rename.log

echo "Renaming done."
cd $localpath