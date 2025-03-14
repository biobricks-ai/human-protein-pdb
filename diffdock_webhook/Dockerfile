# syntax=docker/dockerfile:1
FROM rbgcsail/diffdock

# Ensure we're running as root.
USER 0

# Install curl
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container.
WORKDIR /home/appuser/DiffDock

# Copy the service file and local protein files into the container.
COPY diffdock_docking_service.py /home/appuser/DiffDock

# Copy protein folder 
COPY local_proteins/ /home/appuser/DiffDock/local_proteins/

## Copy the CSV mapping file.
#COPY rename_mapping.csv /app/rename_mapping.csv
#
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

# Expose the port that uvicorn will listen on.
EXPOSE 8000

# Override the default entrypoint.
ENTRYPOINT []

# Start the uvicorn server in the foreground.
CMD /bin/bash -c "micromamba run -n diffdock uvicorn diffdock_docking_service:app --host 0.0.0.0 --port 8000 --reload"
## Start the uvicorn server in the background.
#CMD /bin/bash -c "nohup uvicorn diffdock_docking_service:app --host 0.0.0.0 --port 8000 --reload 2>&1 &"

