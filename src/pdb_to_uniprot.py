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
    result_url = f'https://rest.uniprot.org/idmapping/status/{job_id}'
    while True:
        status_response = requests.get(result_url).json()
        if status_response.get('jobStatus') == 'RUNNING':
            time.sleep(3)
        elif status_response.get('jobStatus') == 'FINISHED':
            break
        else:
            raise Exception(f"Job failed: {status_response}")

    # Get results
    results_link = status_response['results']
    results_response = requests.get(results_link).json()

    # Convert results to a DataFrame
    mappings = []
    for result in results_response['results']:
        pdb_id = result['from']
        uniprot_id = result['to']['primaryAccession']
        mappings.append({'PDB_ID': pdb_id, 'UniProt_ID': uniprot_id})

    df = pd.DataFrame(mappings)
    return df


def rename_files(directory, pdb_ids):
    df_mapping = map_pdb_to_uniprot(pdb_ids)

    for _, row in df_mapping.iterrows():
        pdb_id = row['PDB_ID'].lower()
        uniprot_id = row['UniProt_ID']
        
        old_filename = os.path.join(directory, f'pdb{pdb_id}.pdb')
        new_filename = os.path.join(directory, f'{uniprot_id}.pdb')

        # Check if file exists before renaming
        if os.path.isfile(old_filename):
            os.rename(old_filename, new_filename)
            # print(f'Renamed {old_filename} -> {new_filename}')
        else:
            print(f'File {old_filename} not found.')


def get_pdb_ids(directory):
    # pdb_ids = ['1CBS', '4HHB', '1STP']  # Example list of PDB IDs
    pdb_ids = glob.glob(directory + '*.gz')

    # prefix_length = len('pdb')
    # # filename format is "pdb{id}.{extension}", so isolate "{id}" and make it uppercase
    # pdb_ids = [os.path.basename(pdb_id)[prefix_length:].split('.')[0].upper() for pdb_id in pdb_ids]

    # filename format is "{id}.{extension}", so isolate "{id}" and make it uppercase
    pdb_ids = [os.path.basename(pdb_id).split('.')[0].upper() for pdb_id in pdb_ids]
    return pdb_ids


def main():
    # Directory containing pdb files
    directory = './download/'
    pdb_ids = get_pdb_ids(directory)
    rename_files(directory, pdb_ids)


if __name__ == '__main__':
    main()