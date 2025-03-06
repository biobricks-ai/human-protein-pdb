import requests
from tqdm import tqdm

# Read the file "fname", which contains a single line of comma-separated PDB IDs
#fname = 'missing_pdb_ids.txt'
fname = 'pdb_ids.txt'
with open(fname, 'r') as file:
    content = file.read().strip()
    pdb_ids = content.split(',')

# Function to check validity of a PDB ID using RCSB's API
def is_valid_pdb_id(pdb_id):
    url = f"https://data.rcsb.org/rest/v1/core/structure/{pdb_id}"
    response = requests.get(url)
    return response.status_code == 200

# Perform validation
#invalid_pdb_ids = [pdb_id for pdb_id in pdb_ids if not is_valid_pdb_id(pdb_id)]
invalid_pdb_ids = []
for pdb_id in tqdm(pdb_ids, desc = "Validating PDB IDs"):
    if not is_valid_pdb_id(pdb_id):
        invalid_pdb_ids.append(pdb_id)

# Report
print(f"Total Downloads: {len(pdb_ids)}")
print(f"Invalid PDB IDs: {len(invalid_pdb_ids)}")
print(f"Percentage Invalid: {len(invalid_pdb_ids) / len(pdb_ids) * 100:.2f}%")
print("Sample Invalid PDB IDs:", invalid_pdb_ids[:10])
