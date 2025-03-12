#!/usr/bin/env python3

import os
import sys
import time
import requests
import argparse
from tqdm import tqdm

# Base URL for PDB structure files
BASE_URL = "https://files.rcsb.org/pub/pdb/data/structures/all"

# Track PDB IDs that fail (due to missing files, failed downloads, etc.)
failed_pdbs = set()

# Centralized file extensions mapping for different file types
def get_extensions():
    base_name = "pdb{pdb_id}"
    return {
        'cif': f"{base_name}.cif.gz",
        'pdb': f"{base_name}.ent.gz",
        'pdb1': f"{base_name}.pdb1.gz",
        'cifassembly1': f"{base_name}-assembly1.cif.gz",
        'xml': f"{base_name}.xml.gz",
        'sf': f"{base_name}-sf.cif.gz",
        'mr': f"{base_name}.mr.gz",
        'mrstr': f"{base_name}_mr.str.gz"
    }

# Query RCSB API to get experimental methods for a given PDB ID
def get_experiment_type(pdb_id):
    url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            methods = [expt['method'] for expt in data.get('exptl', [])]
            return methods
        except requests.RequestException as e:
            print(f"Warning: Attempt {attempt+1}/3 - Could not fetch metadata for {pdb_id}: {e}")
            time.sleep(2**attempt*0.1)  # Exponential backoff with small base time
    print(f"Failed to fetch metadata for {pdb_id} after 3 attempts. Skipping.")
    failed_pdbs.add(pdb_id)
    return []

# Check if a structure should be skipped based on being EM-only (no atomic model)
def should_skip_due_to_em(methods):
    methods = set(m.upper() for m in methods)
    return methods == {"ELECTRON MICROSCOPY"}  # Skip pure EM entries
    
# Check if a specific file type exists for a PDB ID before downloading
# This reduces unnecessary 403 errors
def file_type_available(pdb_id, filetype):
    extensions = get_extensions()
    filename = extensions.get(filetype).format(pdb_id=pdb_id)

    if not filename:
        return True  # If filetype isn't handled here, assume it's available

    url = f"{BASE_URL}/{filetype}/{filename}"
    response = requests.head(url)
    return response.status_code == 200

# Check if file already exists locally to avoid redundant downloads
def file_already_downloaded(pdb_id, filetype, outdir):
    extensions = get_extensions()
    filename = extensions[filetype].format(pdb_id=pdb_id)
    outpath = os.path.join(outdir, filename)
    return os.path.exists(outpath)

# Download a file via HTTP
def download_file(pdb_id, filetype, outdir):
    if file_already_downloaded(pdb_id, filetype, outdir):
        #print(f"Skipping {pdb_id} - {filetype} already exists")
        return

    extensions = get_extensions()
    filename = extensions[filetype].format(pdb_id=pdb_id)
    url = f"{BASE_URL}/{filetype}/{filename}"
    outpath = os.path.join(outdir, filename)

    if not file_type_available(pdb_id, filetype):
        print(f"Skipping {pdb_id} - {filetype} file does not exist")
        failed_pdbs.add(pdb_id)
        return

    for attempt in range(3):
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            with open(outpath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return  # Success
        except requests.RequestException as e:
            print(f"Warning: Attempt {attempt+1}/3 - Failed to download {pdb_id} ({filetype}): {e}")
            time.sleep(2**attempt)
    print(f"Failed to download {pdb_id} ({filetype}) after 3 attempts.")
    failed_pdbs.add(pdb_id)

# Download a file using rsync
def rsync_file(pdb_id, filetype, outdir):
    if file_already_downloaded(pdb_id, filetype, outdir):
        print(f"Skipping {pdb_id} - {filetype} already exists")
        return

    extensions = get_extensions()
    filename = extensions[filetype].format(pdb_id=pdb_id)
    remote_path = f"rsync.wwpdb.org::ftp/data/structures/all/{filetype}/{filename}"
    local_path = os.path.join(outdir, filename)

    try:
        result = os.system(f"rsync -rlpt --timeout=30 {remote_path} {local_path}")
        if result != 0:
            raise RuntimeError(f"rsync failed for {pdb_id} ({filetype})")
    except Exception as e:
        print(f"Failed to rsync {pdb_id} ({filetype}): {e}")
        failed_pdbs.add(pdb_id)

# Main driver for parsing args and processing PDB IDs
def main():
    parser = argparse.ArgumentParser(description="Download files from RCSB.")
    parser.add_argument('-f', required=True, help="Input file with comma-separated PDB IDs")
    parser.add_argument('-o', default=".", help="Output directory")
    parser.add_argument('-c', action='store_true', help="Download cif.gz files")
    parser.add_argument('-p', action='store_true', help="Download pdb.gz files")
    parser.add_argument('-a', action='store_true', help="Download pdb1.gz files")
    parser.add_argument('-A', action='store_true', help="Download assembly1.cif.gz files")
    parser.add_argument('-x', action='store_true', help="Download xml.gz files")
    parser.add_argument('-s', action='store_true', help="Download sf.cif.gz files")
    parser.add_argument('-m', action='store_true', help="Download mr.gz files")
    parser.add_argument('-r', action='store_true', help="Download mr.str.gz files")
    parser.add_argument('--rsync', action='store_true', help="Use rsync instead of HTTP")

    args = parser.parse_args()
    os.makedirs(args.o, exist_ok=True)

    with open(args.f, 'r') as f:
        pdb_ids = f.read().strip().split(',')

    for pdb_id in tqdm(pdb_ids, desc="Processing PDB IDs", unit="file"):
        experiment_methods = get_experiment_type(pdb_id)
        if should_skip_due_to_em(experiment_methods):
            print(f"Skipping {pdb_id} - Electron Microscopy only (no atomic model)")
            continue

        download_func = rsync_file if args.rsync else download_file

        if args.c:
            download_func(pdb_id, 'cif', args.o)
        if args.p:
            download_func(pdb_id, 'pdb', args.o)
        if args.a:
            download_func(pdb_id, 'pdb1', args.o)
        if args.A:
            download_func(pdb_id, 'cifassembly1', args.o)
        if args.x:
            download_func(pdb_id, 'xml', args.o)
        if args.s:
            download_func(pdb_id, 'sf', args.o)
        if args.m:
            download_func(pdb_id, 'mr', args.o)
        if args.r:
            download_func(pdb_id, 'mrstr', args.o)

    if failed_pdbs:
        with open('failed_pdb_ids.txt', 'w') as f:
            f.write(','.join(failed_pdbs) + '\n')
        print(f"Failed PDB IDs written to 'failed_pdb_ids.txt'")

if __name__ == "__main__":
    main()
