#!/usr/bin/env bash
set -euo pipefail

# ---Configuration-----------------
SFTP_HOST="localhost"
SFTP_PORT="2222"
SFTP_USER="sftpuser"
SFTP_KEY="${HOME:-/home/blasley}/.ssh/sftp_demo_key"
REMOTE_DIR="uploads"
LOCAL_DIR="${HOME:-/home/blasley}/sftp-outbox"
GPG_RECIPIENT="sftp-server@demo.local"
LOG_FILE="${HOME:-/home/blasley}/sftp-demo/transfer.log"

log() { echo "[$(date -Iseconds)] $1" | tee -a "$LOG_FILE"; }

# ---Ensure dirs exist-------------
mkdir -p "$LOCAL_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# ---Check for Files to Send------
shopt -s nullglob
files=("$LOCAL_DIR"/*)
shopt -u nullglob

if [[ ${#files[*]} -eq 0 ]]; then
  echo "No files to transfer in $LOCAL_DIR"
  exit 0
fi

log "Starting transfer job — ${#files[*]} files in outbox"

# ---PGP Encrypt Files------------
echo "Encrypting files with PGP..."
encrypted_files=()
for file in "${files[@]}"; do
  gpg --batch --yes --trust-model always \
      --recipient "$GPG_RECIPIENT" \
      --output "${file}.gpg" \
      --encrypt "$file"
  echo "  Encrypted: $(basename "$file") -> $(basename "$file").gpg"
  encrypted_files+=("${file}.gpg")
done
log "Encrypted ${#encrypted_files[*]} files"

# ---Generate Integrity Manifest---
manifest="$LOCAL_DIR/MANIFEST.sha256"
(cd "$LOCAL_DIR" && sha256sum *.gpg > MANIFEST.sha256)
echo "  Generated SHA-256 checksum manifest"
encrypted_files+=("$manifest")
log "Generated integrity manifest (SHA-256)"

#---Build SFTP Batch Command-----
batch_file=$(mktemp)
echo "cd $REMOTE_DIR" >"$batch_file"

for file in "${encrypted_files[@]}"; do
  echo "put \"$file\"" >>"$batch_file"
  echo "  Queued: $(basename "$file")"
done

echo "ls" >>"$batch_file"

#----Execute Transfer------
log "Connecting to $SFTP_HOST:$SFTP_PORT as $SFTP_USER..."
if sftp -P "$SFTP_PORT" -i "$SFTP_KEY" -b "$batch_file" "$SFTP_USER@$SFTP_HOST"; then
  log "Transfer complete — ${#encrypted_files[*]} files delivered"
  echo "Cleaning up outbox..."
  for file in "${files[@]}"; do
    rm -f "$file" "${file}.gpg"
    echo "  Removed: $(basename "$file") + .gpg"
  done
  rm -f "$manifest"
else
  log "TRANSFER FAILED"
  echo "Transfer failed!"
  for file in "${encrypted_files[@]}"; do
    rm -f "$file"
  done
  rm "$batch_file"
  exit 1
fi

rm "$batch_file"
log "Job complete"
echo "Done."
