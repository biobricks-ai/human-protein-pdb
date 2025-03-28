#!/usr/bin/env bash

# Script to move proteins with UniProt ID to the diffdock_webhook

# Get local path
local_path=$(pwd)
source_path="$local_path/download"
destination_path="$local_path/diffdock_webhook/local_proteins"

mv $source_path/*.pdb.gz $destination_path

echo "Moving done."
