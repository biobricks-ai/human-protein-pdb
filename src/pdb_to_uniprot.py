import os
import requests
import time
import glob
import pandas as pd

'''
Note:
    Some PDB IDs map to multiple UniProt IDs (in multi-chain structures), resulting in ambiguities.
    The provided method maps PDB IDs to the primary UniProt accession.
    You may need manual verification or more detailed chain-specific mappings via RCSB PDB API if needed.
'''

def map_pdb_to_uniprot(pdb_ids):
    url = 'https://rest.uniprot.org/idmapping/run'
    params = {
        'from': 'PDB',
        'to': 'UniProtKB',
        'ids': ','.join(pdb_ids),
    }
    response = requests.post(url, data=params)
    response.raise_for_status()
    job_id = response.json()['jobId']

    # Check job status until completion
    status_url = f'https://rest.uniprot.org/idmapping/status/{job_id}'
    while True:
        status_response = requests.get(status_url).json()

        job_status = status_response.get('jobStatus')

        if job_status == 'RUNNING':
            time.sleep(3)
        elif job_status == 'FINISHED' or 'results' in status_response:
            # If finished explicitly or results are available, we break successfully
            warnings = status_response.get('warnings', [])
            failed_ids = status_response.get('failedIds', [])
            if warnings:
                print(f"API returned warnings: {warnings}")
            if failed_ids:
                print(f"API failed to map these IDs: {failed_ids}")
            break
        else:
            raise Exception(f"Job failed or returned unexpected status: {status_response}")

    # Continue fetching results explicitly
    results_url = f'https://rest.uniprot.org/idmapping/uniprotkb/results/{job_id}'
    results_response = requests.get(results_url).json()

    # # Get results
    # # results_link = status_response['results']
    # # results_response = requests.get(results_link).json()
    # results_url = f'https://rest.uniprot.org/idmapping/uniprotkb/results/{job_id}'
    # results_response = requests.get(results_url).json()

    # Convert results to a DataFrame
    mappings = []
    for result in results_response['results']:
        pdb_id = result['from']
        uniprot_id = result['to']['primaryAccession']
        mappings.append({'PDB_ID': pdb_id, 'UniProt_ID': uniprot_id})

    df = pd.DataFrame(mappings)
    return df


def sifts_remap(unmapped_ids, sifts_df):
    remapped = {}
    for pdb_id in unmapped_ids:
        matches = sifts_df[sifts_df['PDB'] == pdb_id.lower()]
        if not matches.empty:
            remapped[pdb_id] = matches['SP_PRIMARY'].iloc[0]  # Using the first available UniProt mapping
    return remapped


def rename_files(directory, fnames, pdb_ids, sifts_df):
    df_mapping = map_pdb_to_uniprot(pdb_ids)
    mapping_dict = dict(zip(df_mapping['PDB_ID'].str.upper(), df_mapping['UniProt_ID']))

    unmapped_ids = []

    # Identify IDs not mapped by UniProt
    for pdb_id, fname in zip(pdb_ids, fnames):
        uniprot_id = mapping_dict.get(pdb_id)
        if uniprot_id:
            new_fname = os.path.join(directory, f'{uniprot_id}.pdb')
            if os.path.isfile(fname):
                os.rename(fname, new_fname)
                # print(f'Renamed {fname} -> {new_fname}')  # Uncomment for verbose output
            else:
                print(f'File {fname} not found, skipping.')
        else:
            unmapped_ids.append((pdb_id, fname))
            print(f'No UniProt ID found for {pdb_id}, will try SIFTS.')

    # Attempt SIFTS remapping for remaining unmapped IDs
    if unmapped_ids:
        pdb_ids_unmapped_only = [pid for pid, _ in unmapped_ids]
        sifts_mappings = sifts_remap(pdb_ids_unmapped_only, sifts_df)

        still_unmapped_ids = []
        for pdb_id, fname in unmapped_ids:
            if pdb_id in sifts_mappings:
                uniprot_id = sifts_mappings[pdb_id]
                new_fname = os.path.join(directory, f'{uniprot_id}.pdb')
                if os.path.isfile(fname):
                    os.rename(fname, new_fname)
                    print(f'SIFTS remapped {fname} -> {new_fname}')
                else:
                    print(f'SIFTS mapping file {fname} not found, skipping.')
            else:
                print(f'No SIFTS mapping found for {pdb_id}, skipping.')
                still_unmapped_ids.append(pdb_id)

        # Write IDs that are still unmapped after SIFTS to the CSV
        if still_unmapped_ids:
            with open('unmapped_ids.csv', 'a') as f:
                for id in still_unmapped_ids:
                    f.write(f"{id}\n")


def get_pdb_ids(directory):
    # pdb_ids = ['1CBS', '4HHB', '1STP']  # Example list of PDB IDs
    fnames = glob.glob(directory + '*.gz')

    # exclude filenames with pdb.gz extension
    for i in range(len(fnames) - 1, -1, -1):  # Iterate in reverse order
        if 'pdb.gz' in fnames[i]:
            fnames.pop(i)

    # prefix_length = len('pdb')
    # # filename format is "pdb{id}.{extension}", so isolate "{id}" and make it uppercase
    # pdb_ids = [os.path.basename(pdb_id)[prefix_length:].split('.')[0].upper() for pdb_id in pdb_ids]

    # filename format is "{id}.{extension}", so isolate "{id}" and make it uppercase
    pdb_ids = [os.path.basename(pdb_id).split('.')[0].upper() for pdb_id in fnames]
    return fnames, pdb_ids


def batch_iterable(iterable, batch_size):
    for i in range(0, len(iterable), batch_size):
        yield iterable[i:i + batch_size]


def main():
    # Directory containing gzipped pdb files
    directory = './'
    fnames, pdb_ids = get_pdb_ids(directory)

    # Load SIFTS mappings (ensure this file is downloaded and placed in working directory)
    sifts_df = pd.read_csv('pdb_chain_uniprot.tsv', sep='\t', skiprows=1,
                           names=['PDB', 'CHAIN', 'SP_PRIMARY', 'RES_BEG', 'RES_END', 
                                  'PDB_BEG', 'PDB_END', 'SP_BEG', 'SP_END'])

    # Batch process to avoid hitting API rate limits
    indices = list(range(len(pdb_ids)))
    batch_size = 500  # Adjust as needed

    for batch_indices in batch_iterable(indices, batch_size):
        batch_fnames = [fnames[i] for i in batch_indices]
        batch_pdb_ids = [pdb_ids[i] for i in batch_indices]

        rename_files(directory, batch_fnames, batch_pdb_ids, sifts_df)

    # rename_files(directory, fnames, pdb_ids)  # Uncomment for single batch processing


if __name__ == '__main__':
    main()