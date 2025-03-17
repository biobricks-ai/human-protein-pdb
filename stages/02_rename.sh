#!/usr/bin/env bash

# Script to rename files from PDB ID -> UniProt ID

# Get local path
localpath=$(pwd)
srcpath=$(pwd)/src
downloadpath="$localpath/download"

echo "Local path: $localpath"
echo "Download path: $downloadpath"

cd $downloadpath

# Run renaming script within the download directory
python $srcpath/pdb_to_uniprot.py | tee rename.log

echo "Renaming done."
cd $localpath