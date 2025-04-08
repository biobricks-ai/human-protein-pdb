# syntax=docker/dockerfile:1
FROM rbgcsail/diffdock

# Ensure we're running as root.
USER 0

# Install system dependencies.
# Use apt-get to install the required packages.
RUN apt-get update && \
apt-get install -y --no-install-recommends \
    curl \
    python3 \
    python3-pip \
    build-essential \
    cmake \
    nvidia-cuda-toolkit && \
rm -rf /var/lib/apt/lists/*

# Upgrade pip and install required Python packages.
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir uvicorn httpx fastapi rdkit

# Set working directory inside the container.
WORKDIR /home/appuser/DiffDock

# Copy the service file and local protein files into the container.
COPY diffdock_docking_service.py /home/appuser/DiffDock

# Create a directory for local protein files.
ENV LOCAL_PROTEIN_DIR=/home/appuser/DiffDock/local_proteins
RUN mkdir -p $LOCAL_PROTEIN_DIR

# Copy protein folder(s) into the container.
# Use a shell command to avoid errors if no files match.
COPY local_proteins/*.pdb local_proteins/*.pdb.gz $LOCAL_PROTEIN_DIR

## Create the target directory and copy files with dereferenced symlinks.
#RUN mkdir -p /app/local_proteins && \
#    cp -aL /tmp/local_proteins/. /app/local_proteins/
#
## Copy and run the renaming script.
#COPY rename_symlinks.sh /tmp/rename_symlinks.sh
#RUN chmod +x /tmp/rename_symlinks.sh && /tmp/rename_symlinks.sh

# Use bash as our shell so we can activate the environment.
SHELL ["/bin/bash", "-c"]

# Initialize the shell and activate the diffdock environment.
RUN eval "$(micromamba shell hook bash)" && micromamba activate diffdock

# Install PyTorch with GPU support (CUDA)
# RUN micromamba run -n diffdock pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118/torch_stable.html
# RUN micromamba run -n diffdock pip install --upgrade --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118/torch_stable.html

# Expose the port that uvicorn will listen on.
EXPOSE 8000

# Override the default entrypoint.
ENTRYPOINT []

# Start the uvicorn server in the foreground.
CMD ["python3", "-m", "uvicorn", "diffdock_docking_service:app", "--host", "0.0.0.0", "--port", "8000"]
# CMD /bin/bash -c "micromamba run -n diffdock uvicorn diffdock_docking_service:app --host 0.0.0.0 --port 8000"
## Start the uvicorn server in the background.
#CMD /bin/bash -c "nohup uvicorn diffdock_docking_service:app --host 0.0.0.0 --port 8000 --reload 2>&1 &"