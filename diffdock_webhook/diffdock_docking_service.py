import asyncio
import re
import glob
import os
import tempfile
import httpx
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Directory where local protein files are stored.
LOCAL_PROTEIN_DIR = "./local_proteins"

class DockingUniProtRequest(BaseModel):
    uniprot_id: str  # The UniProt ID, e.g., A0A4P8L7K3.
    ligand: str      # The ligand as a SMILES string.
    callback_url: str  # The URL where the client will receive the docking results.

@app.post("/start_docking_uniprot")
async def start_docking_uniprot(request: DockingUniProtRequest, background_tasks: BackgroundTasks):
    """
    Endpoint to start the docking process using a UniProt ID. The server searches the local protein
    directory for a file named '<uniprot_id>.pdb'. If found, its path is used for the DiffDock command.
    Otherwise, an exception is thrown.
    """
    protein_file_path = os.path.join(LOCAL_PROTEIN_DIR, f"{request.uniprot_id}.pdb")
    if not os.path.exists(protein_file_path):
        raise HTTPException(status_code=404, detail=f"Protein file for UniProt ID {request.uniprot_id} not found.")
    
    background_tasks.add_task(process_docking_request_uniprot, request.callback_url, protein_file_path, request.ligand)
    return {
        "message": "Docking task started. You will be notified at your callback URL upon completion."
    }

async def perform_docking_uniprot(protein_file_path: str, ligand: str) -> dict:
    """
    Performs the docking process using DiffDock for a protein file provided by a UniProt ID.
    
    The Docker container is assumed to be always running. The command is executed as:
    
        python -m inference --config default_inference_args.yaml --protein_path "<protein_file_path>"
               --ligand "<ligand>" --out_dir <temporary_directory>/
    
    After execution, the temporary output directory will contain a folder named 'complex_0' with a file 
    named like 'rank1_confidence0.17.sdf'. This function extracts the docking score from the filename and 
    reads the entire file content as the pose.
    """
    with tempfile.TemporaryDirectory() as tmpdirname:
        output_dir = tmpdirname  # Use the temporary directory for docking results.
        command = [
            "python", "-m", "inference",
            "--config", "default_inference_args.yaml",
            "--protein_path", protein_file_path,
            "--ligand", ligand,
            "--out_dir", output_dir
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise Exception(f"DiffDock failed with error: {stderr.decode()}")
        
        # The results are expected in the 'complex_0' subdirectory.
        complex_dir = os.path.join(output_dir, "complex_0")
        files = glob.glob(os.path.join(complex_dir, "rank1_confidence*.sdf"))
        if not files:
            raise Exception("Docking output file not found in expected directory.")
        docking_file = files[0]
        
        # Extract the docking score from the filename.
        # Example filename: "rank1_confidence0.17.sdf"
        basename = os.path.basename(docking_file)
        prefix = "rank1_confidence"
        suffix = ".sdf"
        score_str = basename[len(prefix):-len(suffix)]
        docking_score = float(score_str)

        # Add DiffDock's confidence in the pose based on the docking score
        if docking_score > 0.0:
            docking_confidence = "high confidence"
        elif docking_score > -1.5:
            docking_confidence = "moderate confidence"
        else:
            docking_confidence = "low confidence"
        
        # Read the entire file content as the docking pose.
        with open(docking_file, "r") as f:
            pose_contents = f.read()

        # isolate the uniprot_id from the protein_file_path
        match = re.search(r'/([^/]+)\.pdb$', protein_file_path)
        uniprot_id = match.group(1)
        
        docking_result = {
            "docking_score": docking_score,
            "docking_confidence": docking_confidence,
            "pose": pose_contents,
            "uniprot_id": uniprot_id,
            "ligand": ligand
        }
        return docking_result

async def process_docking_request_uniprot(callback_url: str, protein_file_path: str, ligand: str):
    """
    Processes the docking request by performing docking using the provided UniProt protein file and 
    sending the result to the client's callback URL. The temporary directory for docking outputs is 
    automatically deleted once processing is complete.
    """
    try:
        docking_result = await perform_docking_uniprot(protein_file_path, ligand)
        payload = {
            "status": "completed",
            "result": docking_result
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(callback_url, json=payload)
            response.raise_for_status()
    except Exception as e:
        # Handle exceptions (e.g., log or retry as necessary)
        # # Create an error payload to notify the callback URL
        error_payload = {
            "status": "failed",
            "error": str(e),
            "error_code": 500  # You can use any appropriate error code
        }
        async with httpx.AsyncClient() as client:
            try:
                error_response = await client.post(callback_url, json=error_payload)
                error_response.raise_for_status()
            except Exception as post_error:
                # Log the failure to notify the callback URL if necessary
                print(f"Failed to send error callback: {post_error}")
        print(f"Error processing docking request for UniProt: {e}")
