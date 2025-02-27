import os
import glob
import pandas as pd

missing_files_list = sorted(glob.glob("missing_pdb_ids*.txt"))
print("missing files:")
print(missing_files_list)
df = []

for file in missing_files_list:
    df.append( pd.read_csv(file) )

switched_ids = []
for label in df[0]:
    if label not in df[1]:
        switched_ids.append(label)

print("switched ids:")
print(switched_ids)
