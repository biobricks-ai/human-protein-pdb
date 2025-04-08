#!/usr/bin/env bash

# Script to rename files from PDB ID -> UniProt ID

# Get local path
localpath=$(pwd)
srcpath=$(pwd)/src
downloadpath="$localpath/download"

echo "Local path: $localpath"
echo "Download path: $downloadpath"

cd $downloadpath

# Remove "pdb" prefix from filenames
for file in pdb*; do
    newfile=$(echo "$file" | sed 's/^pdb//')
    mv "$file" "$newfile"
done

# Run renaming script within the download directory
python $srcpath/pdb_to_uniprot.py $srcpath 2>&1 | tee rename.log

echo "Renaming done."
cd $localpath