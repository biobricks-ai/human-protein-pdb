# diffdock_with_celery.py
import os
import re
import glob
import gzip
import shutil
import tempfile
import traceback
import subprocess
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from rdkit import Chem
from celery import Celery
from celery.result import AsyncResult

# ----------------------------------------------------------------
# Celery configuration (Redis broker & backend by default)
# ----------------------------------------------------------------
CELERY_BROKER_URL      = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND  = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

celery_app = Celery(
    'diffdock_tasks',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# ----------------------------------------------------------------
# FastAPI application
# ----------------------------------------------------------------
app = FastAPI(
    title="Diffdock with Celery",
    description="Dock small molecules onto human proteins using DiffDock, queued via Celery.",
    version="1.0.0",
)

LOCAL_PROTEIN_DIR = './local_proteins'

# ----------------------------------------------------------------
# Pydantic request model
# ----------------------------------------------------------------
class DockingUniProtRequest(BaseModel):
    uniprot_id:  str
    ligand:      str
    callback_url: str

# ----------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------
def is_valid_smiles(smiles: str) -> bool:
    return Chem.MolFromSmiles(smiles) is not None

def uniprot_id_from_path(protein_file_path: str) -> str:
    m = re.search(r'/([^/]+)\.pdb$', protein_file_path)
    if not m:
        raise ValueError("Invalid protein file path")
    return m.group(1)

def _prepare_protein(uniprot_id: str) -> str:
    """Locate .pdb or unzip .pdb.gz into LOCAL_PROTEIN_DIR."""
    pdb = os.path.join(LOCAL_PROTEIN_DIR, f"{uniprot_id}.pdb")
    gz  = pdb + '.gz'
    if not os.path.exists(pdb):
        if not os.path.exists(gz):
            raise FileNotFoundError(f"No PDB or PDB.GZ for {uniprot_id}")
        with gzip.open(gz, 'rb') as fin, open(pdb, 'wb') as fout:
            shutil.copyfileobj(fin, fout)
    if os.path.getsize(pdb) < 500:
        raise ValueError(f"PDB file for {uniprot_id} is too small")
    return pdb

def _run_diffdock_sync(protein_path: str, ligand: str) -> dict:
    """
    Synchronous version of your perform_docking_uniprot:
    runs `python -m inference`, parses the rank1_confidence*.sdf result.
    """
    workdir = tempfile.mkdtemp()
    cmd = [
        'python', '-m', 'inference',
        '--config', 'default_inference_args.yaml',
        '--protein_path', protein_path,
        '--ligand', ligand,
        '--out_dir', workdir
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode())

    comp_dir = os.path.join(workdir, 'complex_0')
    files = glob.glob(os.path.join(comp_dir, 'rank1_confidence*.sdf'))
    if not files:
        raise RuntimeError("No docking pose generated")

    sdf = files[0]
    score_str = sdf.split('rank1_confidence',1)[1].rsplit('.sdf',1)[0]
    score = float(score_str)
    confidence = (
        'high confidence'     if score > 0.0
        else 'moderate confidence' if score > -1.5
        else 'low confidence'
    )
    with open(sdf, 'r') as f:
        pose = f.read()

    return {
        'uniprot_id':   uniprot_id_from_path(protein_path),
        'ligand':       ligand,
        'docking_score':score,
        'docking_confidence': confidence,
        'pose':         pose
    }

# ----------------------------------------------------------------
# Celery task
# ----------------------------------------------------------------
@celery_app.task(bind=True)
def dock_task(self, uniprot_id: str, ligand: str, callback_url: str) -> dict:
    """
    Celery task: prepare protein, run docking, POST to callback_url.
    """
    start = datetime.utcnow().isoformat()
    try:
        pdb = _prepare_protein(uniprot_id)
        result = _run_diffdock_sync(pdb, ligand)

        payload = {'status': 'completed', 'result': result}
        httpx.post(callback_url, json=payload).raise_for_status()

        return {'task_id': self.request.id, 'status': 'completed', 'started_at': start}

    except Exception as exc:
        tb = traceback.format_exc()
        err_payload = {'status': 'failed', 'error': str(exc), 'traceback': tb}
        try:
            httpx.post(callback_url, json=err_payload)
        except Exception:
            pass
        raise

# ----------------------------------------------------------------
# FastAPI endpoints
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

@app.post("/start_docking_uniprot")
def enqueue_docking(request: DockingUniProtRequest):
    if not is_valid_smiles(request.ligand):
        raise HTTPException(status_code=400, detail="Invalid SMILES string")
    task = dock_task.delay(request.uniprot_id, request.ligand, request.callback_url)
    return {"task_id": task.id, "status": "queued"}

@app.get("/jobs/{task_id}")
def get_job_status(task_id: str):
    res = AsyncResult(task_id, app=celery_app)
    payload = {"task_id": task_id, "status": res.status}
    if res.status == 'SUCCESS':
        payload["result"] = res.result
    elif res.status == 'FAILURE':
        payload["error"] = str(res.result)
    return JSONResponse(payload)
