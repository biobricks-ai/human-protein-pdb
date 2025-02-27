import os
import pandas as pd

full_csv = "pdb_ids.txt"
df = pd.read_csv(full_csv)
print(f"Loaded {full_csv}")

missing_files = []
for label in df:
    file = f"../download/{label}.ent.gz"
    if not os.path.exists(file):
        missing_files.append(label)

n_missing = len(missing_files)
print(f"{n_missing} missing files identified")

missing_csv = "missing_pdb_ids.txt"
with open(missing_csv, "w") as fo:
    for n, pdb in enumerate(missing_files):
        if n < n_missing - 1: 
            fo.write(pdb + ",")
        else:
            fo.write(pdb)

print(f"{missing_csv} written")
