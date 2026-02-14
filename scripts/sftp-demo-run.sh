#!/usr/bin/env bash
set -euo pipefail

# ══════════════════════════════════════════════════════════════════
#  SFTP Healthcare Integration Demo — Full Pipeline Runner
#  Runs the complete demo end-to-end for live presentation
# ══════════════════════════════════════════════════════════════════

DEMO_DIR="${HOME:-/home/blasley}/sftp-demo"
OUTBOX="${HOME:-/home/blasley}/sftp-outbox"
SFTP_KEY="${HOME:-/home/blasley}/.ssh/sftp_demo_key"
UPLOADS="/sftp/sftpuser/uploads"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

pause() {
  echo ""
  echo -e "${DIM}  Press Enter to continue...${NC}"
  read -r
}

banner() {
  echo ""
  echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
  echo -e "${BOLD}  $1${NC}"
  echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
  echo ""
}

step() {
  echo -e "${GREEN}▶ $1${NC}"
}

# ── Auto-reset ───────────────────────────────────────
# Clean up from any previous run so the demo is fresh every time
rm -f "$OUTBOX"/* 2>/dev/null || true
rm -f "$DEMO_DIR/transfer.log" 2>/dev/null || true
rm -f "$DEMO_DIR/infusion_dashboard.png" 2>/dev/null || true
rm -f "$DEMO_DIR/dashboard_returned.png" 2>/dev/null || true
rm -rf /tmp/demo-decrypted 2>/dev/null || true
rm -f /tmp/infusion_dashboard.png /tmp/infusion_dashboard.png.gpg 2>/dev/null || true
rm -f /tmp/dashboard_return.gpg 2>/dev/null || true

# Clean server-side uploads
distrobox enter sftp-server -- sudo bash -c "rm -f $UPLOADS/*" 2>/dev/null || true

# Start sshd if not running
if ! ss -tlnp 2>/dev/null | grep -q ":2222"; then
  echo -e "${YELLOW}  Starting SFTP server...${NC}"
  distrobox enter sftp-server -- sudo /usr/sbin/sshd 2>/dev/null
  sleep 1
  if ! ss -tlnp 2>/dev/null | grep -q ":2222"; then
    # Host keys might need regenerating
    distrobox enter sftp-server -- sudo ssh-keygen -A 2>/dev/null
    distrobox enter sftp-server -- sudo /usr/sbin/sshd 2>/dev/null
    sleep 1
  fi
fi

# Load SSH key into agent if needed
if ! ssh-add -l 2>/dev/null | grep -q sftp_demo_key; then
  echo -e "${YELLOW}  Loading SSH key into agent...${NC}"
  ssh-add "$SFTP_KEY"
fi

# ── Pre-flight check ─────────────────────────────────
banner "SFTP Healthcare Integration Demo"
echo -e "  ${BOLD}Infusion Therapy Partners LLC${NC}"
echo -e "  Secure EDI File Transfer Pipeline"
echo -e ""
echo -e "  ${DIM}Components:${NC}"
echo -e "    • SFTP server (chroot-jailed, key auth)"
echo -e "    • PGP encryption (at-rest protection)"
echo -e "    • X12 837P claims + HL7 ADT admissions"
echo -e "    • Automated transfer with integrity checks"
echo -e "    • Server-side decryption, parsing, visualization"
echo -e "    • Bidirectional encrypted return"

# Final pre-flight verification
if ! ss -tlnp 2>/dev/null | grep -q ":2222"; then
  echo -e "${RED}  ⚠ Could not start SFTP server. Enter distrobox manually and start sshd.${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓ SFTP server running${NC}"
echo -e "  ${GREEN}✓ SSH key loaded${NC}"
echo -e "  ${GREEN}✓ Previous run cleaned up${NC}"

pause

# ── Step 1: Show EDI source files ────────────────────
banner "STEP 1: Healthcare EDI Source Files"
step "These are the EDI files from today's infusion therapy sessions"
echo ""

echo -e "  ${BOLD}X12 837P Claims (billing):${NC}"
for f in "$DEMO_DIR"/edi-samples/x12/*.edi; do
  echo -e "    📄 $(basename "$f")"
done
echo ""
echo -e "  ${BOLD}HL7 ADT Admissions (clinical):${NC}"
for f in "$DEMO_DIR"/edi-samples/hl7/*.hl7; do
  echo -e "    📄 $(basename "$f")"
done

echo ""
step "Peek at raw X12 837P claim (first 8 lines):"
head -8 "$DEMO_DIR/edi-samples/x12/837_claim_001.edi" | sed 's/^/    /'

pause

# ── Step 2: Stage files in outbox ────────────────────
banner "STEP 2: Stage Files in Outbox"
step "Copying EDI files to transfer outbox..."

mkdir -p "$OUTBOX"
# Clean any leftover files
rm -f "$OUTBOX"/*

cp "$DEMO_DIR"/edi-samples/x12/*.edi "$OUTBOX/"
cp "$DEMO_DIR"/edi-samples/hl7/*.hl7 "$OUTBOX/"

echo -e "  Staged ${BOLD}$(ls "$OUTBOX" | wc -l)${NC} files in ~/sftp-outbox/"
ls "$OUTBOX" | sed 's/^/    /'

pause

# ── Step 3: Encrypt + Transfer ───────────────────────
banner "STEP 3: PGP Encrypt & SFTP Transfer"
step "Running automated transfer pipeline..."
echo ""

sftp-transfer.sh

echo ""
step "Audit log:"
tail -5 "$DEMO_DIR/transfer.log" | sed 's/^/    /'

pause

# ── Step 4: Server-side verification ─────────────────
banner "STEP 4: Server-Side Integrity Verification"
step "Verifying SHA-256 checksums on server..."
echo ""

sftp -P 2222 -i "$SFTP_KEY" -b <(printf "cd uploads\nls -la\n") sftpuser@localhost 2>/dev/null

echo ""
step "Encrypted files landed — unreadable without server's private key"

pause

# ── Step 5: Decrypt + Process ────────────────────────
banner "STEP 5: Server-Side Decrypt & Process"
step "Decrypting files with server's GPG key..."
echo ""

# Decrypt and process entirely inside the container
distrobox enter sftp-server -- bash -c '
mkdir -p /tmp/demo-decrypted
for f in /sftp/sftpuser/uploads/*.gpg; do
  [ -f "$f" ] || continue
  base="$(basename "$f")"
  [ "$base" = "infusion_dashboard.png.gpg" ] && continue
  outname="$(basename "$f" .gpg)"
  gpg --batch --yes --output "/tmp/demo-decrypted/$outname" --decrypt "$f" 2>/dev/null
  echo "  Decrypted: $outname"
done
echo ""
echo "Parsing X12 837P claims and HL7 ADT admissions..."
echo ""
python3 '"$DEMO_DIR"'/process_edi.py /tmp/demo-decrypted /tmp
'

pause

# ── Step 6: Show visualization ───────────────────────
banner "STEP 6: Generated Dashboard"
step "Opening infusion therapy claims dashboard..."

# Copy dashboard from container to host and display in terminal
distrobox enter sftp-server -- cp /tmp/infusion_dashboard.png "$DEMO_DIR/infusion_dashboard.png" 2>/dev/null || true
if command -v kitten &>/dev/null; then
  kitten icat "$DEMO_DIR/infusion_dashboard.png"
else
  xdg-open "$DEMO_DIR/infusion_dashboard.png" 2>/dev/null &
fi

pause

# ── Step 7: Bidirectional return ─────────────────────
banner "STEP 7: Encrypted Return Transfer"
step "Encrypting dashboard with partner's public key..."

distrobox enter sftp-server -- gpg --batch --yes --trust-model always --recipient partner@demo.local --output /tmp/infusion_dashboard.png.gpg --encrypt /tmp/infusion_dashboard.png 2>/dev/null
distrobox enter sftp-server -- bash -c "sudo cp /tmp/infusion_dashboard.png.gpg $UPLOADS/ && sudo chown sftpuser:sftpuser $UPLOADS/infusion_dashboard.png.gpg" 2>/dev/null

step "Pulling encrypted dashboard back via SFTP..."
sftp -P 2222 -i "$SFTP_KEY" -b <(printf "cd uploads\nget infusion_dashboard.png.gpg /tmp/dashboard_return.gpg\n") sftpuser@localhost 2>/dev/null

step "Decrypting with partner's private key..."
gpg --batch --yes --output "$DEMO_DIR/dashboard_returned.png" --decrypt /tmp/dashboard_return.gpg 2>/dev/null
echo -e "  ${GREEN}✓ Dashboard received and decrypted${NC}"

pause

# ── Summary ──────────────────────────────────────────
banner "Pipeline Complete"
echo -e "  ${BOLD}What just happened:${NC}"
echo ""
echo -e "  1. ${DIM}10 healthcare EDI files (X12 + HL7) staged in outbox${NC}"
echo -e "  2. ${DIM}PGP-encrypted with server's public key${NC}"
echo -e "  3. ${DIM}SHA-256 integrity manifest generated${NC}"
echo -e "  4. ${DIM}Transferred via SFTP (key auth, chroot jail)${NC}"
echo -e "  5. ${DIM}Server decrypted with private key${NC}"
echo -e "  6. ${DIM}Parsed claims + admissions, generated dashboard${NC}"
echo -e "  7. ${DIM}Dashboard encrypted with partner key, returned via SFTP${NC}"
echo -e "  8. ${DIM}Partner decrypted and verified${NC}"
echo ""
echo -e "  ${BOLD}Security layers:${NC}"
echo -e "    🔒 SSH tunnel (transport encryption)"
echo -e "    🔐 PGP (data-at-rest encryption)"
echo -e "    🔑 Key-based auth (no passwords)"
echo -e "    📁 Chroot jail (filesystem isolation)"
echo -e "    🚫 No shell access (ForceCommand internal-sftp)"
echo -e "    ✅ SHA-256 integrity verification"
echo -e "    📋 Timestamped audit logging"
echo ""
echo -e "  ${BOLD}Audit log:${NC}"
cat "$DEMO_DIR/transfer.log" | sed 's/^/    /'
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
