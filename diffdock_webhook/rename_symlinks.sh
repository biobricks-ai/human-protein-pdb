#!/bin/bash
set -e

# Path to the CSV mapping file and target directory
MAPPING_FILE="/app/rename_mapping.csv"
TARGET_DIR="/app/local_proteins"

# Skip the header (if present) and process each line.
tail -n +2 "$MAPPING_FILE" | while IFS=, read -r actual desired; do
  # Trim any accidental whitespace
  actual=$(echo "$actual" | xargs)
  desired=$(echo "$desired" | xargs)

  # Construct the source and target paths
  src="${TARGET_DIR}/${actual}"
  dest="${TARGET_DIR}/${desired}"

  if [ -f "$src" ]; then
    echo "Renaming $src to $dest"
    mv "$src" "$dest"
  else
    echo "Warning: Expected file '$src' not found." >&2
  fi
done
