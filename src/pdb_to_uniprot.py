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
        elif job_status == 'FINISHED':
            # Job explicitly completed
            warnings = status_response.get('warnings', [])
            failed_ids = status_response.get('failedIds', [])
            if warnings:
                print(f"API returned warnings: {warnings}")
            if failed_ids:
                print(f"API failed to map these IDs: {failed_ids}")
            break
        else:
            # Check if the response is malformed or unexpected
            raise Exception(f"Job failed or returned unexpected status: {status_response}")

    # Retrieve results explicitly after confirmed completion
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


def rename_files(directory, fnames, pdb_ids):
    df_mapping = map_pdb_to_uniprot(pdb_ids)

    for i, row in df_mapping.iterrows():
        uniprot_id = row['UniProt_ID']
        
        # pdb_id = row['PDB_ID'].lower()
        # old_filename = os.path.join(directory, f'pdb{pdb_id}.pdb')
        old_filename = fnames[i]
        new_filename = os.path.join(directory, f'{uniprot_id}.pdb.gz')

        # Check if file exists before renaming
        if os.path.isfile(old_filename):
            os.rename(old_filename, new_filename)
            # print(f'Renamed {old_filename} -> {new_filename}')
        else:
            print(f'File {old_filename} not found.')


def get_pdb_ids(directory):
    # pdb_ids = ['1CBS', '4HHB', '1STP']  # Example list of PDB IDs
    fnames = glob.glob(directory + '*.gz')

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

    # Batch process to avoid hitting API rate limits
    indices = list(range(len(pdb_ids)))
    batch_size = 10000  # Adjust as needed

    for batch_indices in batch_iterable(indices, batch_size):
        batch_fnames = [fnames[i] for i in batch_indices]
        batch_pdb_ids = [pdb_ids[i] for i in batch_indices]

        rename_files(directory, batch_fnames, batch_pdb_ids)

    # rename_files(directory, fnames, pdb_ids)


if __name__ == '__main__':
    main()