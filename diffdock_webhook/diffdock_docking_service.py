import os
import asyncio
import re
import glob
import tempfile
import httpx
import gzip
import shutil
import traceback

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from rdkit import Chem

# new imports
from celery import Celery
from celery.result import AsyncResult

app = FastAPI(
    title="Diffdock",
    description="Dock small molecules onto human proteins using DiffDock.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ----------------------------------------------------------------
# Celery setup (adjust URLs as needed or via ENV)
# ----------------------------------------------------------------
CELERY_BROKER_URL     = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "diffdock_queue",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# ----------------------------------------------------------------
# Task wrapper
# ----------------------------------------------------------------
@celery_app.task(bind=True)
def dock_job(self, callback_url: str, protein_file_path: str, ligand: str):
    """
    Celery task wrapper around your existing async function.
    """
    # if your process_docking_request_uniprot is async, run it in its own loop:
    asyncio.run(process_docking_request_uniprot(callback_url, protein_file_path, ligand))
    return {"task_id": self.request.id, "status": "dispatched"}

# ----------------------------------------------------------------
# Your existing endpoints (unchanged) + small edits
# ----------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "DiffDock API is running. Use /docs or /health to explore."}

@app.get("/.well-known/tool.json", include_in_schema=False)
async def get_tool_json():
    return JSONResponse({
        "id": "diffdock",
        "name": "DiffDock",
        "description": "Dock small molecules onto human proteins using DiffDock.",
        "publisher": "Insilica, LLC.", 
        "url": "https://diffdock.toxindex.com",
        "apiSpecUrl": "https://diffdock.toxindex.com/openapi.json"
    })

@app.get("/health")
async def health_check():
    return JSONResponse({"status": "OK", "message": "DiffDock API is running"})

LOCAL_PROTEIN_DIR = "./local_proteins"

class DockingUniProtRequest(BaseModel):
    uniprot_id:  str
    ligand:      str
    callback_url:str

@app.post("/start_docking_uniprot")
async def start_docking_uniprot(request: DockingUniProtRequest):
    """
    Enqueue docking via Celery instead of BackgroundTasks.
    """
    if not is_valid_smiles(request.ligand):
        raise HTTPException(400, f"Invalid SMILES: {request.ligand}")

    # your existing file-locating / unzip logic
    protein_file_path = os.path.join(LOCAL_PROTEIN_DIR, f"{request.uniprot_id}.pdb")
    if not os.path.exists(protein_file_path):
        try:
            protein_file_path = unzip_pdb_gz(request.uniprot_id, LOCAL_PROTEIN_DIR, LOCAL_PROTEIN_DIR)
        except FileNotFoundError:
            raise HTTPException(404, f"Protein {request.uniprot_id} not found")
    if os.path.getsize(protein_file_path) < 500:
        raise HTTPException(400, f"PDB for {request.uniprot_id} looks too small")

    # enqueue and return a task ID
    task = dock_job.delay(request.callback_url, protein_file_path, request.ligand)
    return {"message": "Docking enqueued", "task_id": task.id}

@app.get("/jobs/{task_id}")
def get_job_status(task_id: str):
    """
    Simple status endpoint for Celery tasks.
    """
    res = AsyncResult(task_id, app=celery_app)
    data = {"task_id": task_id, "status": res.status}
    if res.status == "SUCCESS":
        data["result"] = res.result
    elif res.status == "FAILURE":
        data["error"] = str(res.result)
    return JSONResponse(data)

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
    uniprot_id = uniprot_id_from_path(protein_file_path)
    print(f"Running docking for UniProt ID: {uniprot_id}, Ligand: {ligand}")

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
        # Print stdout to log
        print("=== DiffDock STDOUT ===")
        print(stdout.decode())
        # Print stderr to log
        print("=== DiffDock STDERR ===")
        print(stderr.decode())
        print("=======================")

        if proc.returncode != 0:
            e = Exception(f"DiffDock failed with return code {proc.returncode}")
            e.stderr = stderr
            e.stdout = stdout  # optional, if you also want to forward stdout
            raise e
        
        # The results are expected in the 'complex_0' subdirectory.
        complex_dir = os.path.join(output_dir, "complex_0")
        if not os.path.exists(complex_dir):
            raise Exception("Docking completed but no pose was generated. This may happen if DiffDock was unable to sample a valid pose for the given protein-ligand pair.")

        files = glob.glob(os.path.join(complex_dir, "rank1_confidence*.sdf"))
        if not files:
            raise Exception("No docking pose was generated. DiffDock may have failed to sample a valid pose for this protein-ligand pair.")
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
        
        docking_result = {
            "docking_score": docking_score,
            "docking_confidence": docking_confidence,
            "pose": pose_contents,
            "uniprot_id": uniprot_id,
            "ligand": ligand
        }
        return docking_result
    
def is_valid_smiles(smiles: str) -> bool:
    return Chem.MolFromSmiles(smiles) is not None

def uniprot_id_from_path(protein_file_path: str) -> str:
    """
    Extracts the UniProt ID from the protein file path.
    """
    match = re.search(r'/([^/]+)\.pdb$', protein_file_path)
    if match:
        return match.group(1)
    else:
        raise ValueError("Invalid protein file path: Unable to extract UniProt ID.")
    
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
        tb_str = traceback.format_exc()
        stderr_info = getattr(e, "stderr", "").decode(errors="ignore") if hasattr(e, "stderr") else ""
        uniprot_id = uniprot_id_from_path(protein_file_path)

        # Create an error payload to notify the callback URL
        error_type = "no_pose_generated" if "No docking pose was generated" in str(e) else "inference_error"
        error_payload = {
            "status": "failed",
            "error_type": error_type,
            "uniprot_id": uniprot_id,
            "ligand": ligand,
            "error": str(e),
            "traceback": tb_str,
            "stderr": stderr_info,
            "error_code": 500
        }
        async with httpx.AsyncClient() as client:
            try:
                error_response = await client.post(callback_url, json=error_payload)
                error_response.raise_for_status()
            except Exception as post_error:
                # Log the failure to notify the callback URL if necessary
                print(f"Failed to send error callback: {post_error}")
        print(f"Error processing docking request for UniProt:\n{tb_str}")

def unzip_pdb_gz(uniprot_id, source_dir, dest_dir):
    """
    Unzips a .pdb.gz file to .pdb.
    """
    pdb_gz_file = os.path.join(source_dir, f"{uniprot_id}.pdb.gz")
    pdb_file = os.path.join(dest_dir, f"{uniprot_id}.pdb")

    print(f"Attempting to unzip {pdb_gz_file} to {pdb_file}")

    if not os.path.exists(pdb_file):
        if not os.path.exists(pdb_gz_file):
            raise FileNotFoundError(f"Source file {pdb_gz_file} not found.")
        
        with gzip.open(pdb_gz_file, 'rb') as f_in:
            with open(pdb_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    return pdb_file