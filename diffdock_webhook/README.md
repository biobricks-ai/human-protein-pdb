The current Docker environment assumes the existence of a local directory of proteins called `local_proteins/`. Each file in `local_proteins/` is a `.pdb` file named `${uniprot_id}.pdb`

Usage:
```
docker build -t diffdock_service .
```
```
docker run -d --name diffdock_service -p 8000:8000 diffdock_service
```
```
curl -X POST "http://127.0.0.1:8000/start_docking_uniprot" \
     -H "Content-Type: application/json" \
     -d '{"uniprot_id": "your_uniprot_id", "ligand": "your_ligand_smiles", "callback_url": "http://your-callback-url/endpoint"}'
```
Replace `your_uniprot_id`, `your_ligand_smiles`, and `http://your-callback-url/endpoint` with the appropriate values.

To check the container log:
```
docker logs -f diffdock_service
```

To stop the running container:
```
docker stop diffdock_service
docker rm -f diffdock_service
```

The files `rename_mapping.csv` and `rename_symlinks.sh` may be useful if `local_proteins/` gets very large so we only need to store symlinks instead of full `.pdb` files. However, this strategy is not yet incorporated.
	
The next objective is to make a GitHub repo with many such proteins and adjust the Python script to search this repo for the appropriate protein file and download it.
