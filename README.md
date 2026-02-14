# SFTP Healthcare Integration Demo

A full end-to-end SFTP integration pipeline for healthcare EDI data, built to demonstrate the technical skills required for a **Technical Implementation Manager** role in healthtech.

This project simulates a realistic bidirectional file exchange between a trading partner (host machine) and an integration server (containerized SFTP server), processing infusion therapy claims and admissions data with enterprise-grade security.

<!-- TODO: Add demo video here -->

---

## What This Demonstrates

| Skill Area | Implementation |
|:--|:--|
| SFTP Connections | SFTP server built from scratch in a containerized environment (distrobox + OpenSSH) |
| Healthcare Data Files | X12 837P professional claims + HL7 ADT admissions with realistic infusion therapy data |
| ETL Pipelines | Python parser that extracts, transforms, and visualizes data from both EDI formats |
| HIPAA / SOC 2 Compliance | PGP encryption (at-rest), SSH tunnel (in-transit), chroot jails, audit logging, SHA-256 checksums |
| Eligibility / Claims / Prior Auth | Simulated full claims lifecycle with CPT codes, ICD-10 diagnoses, J-codes, and payer data |
| Automation | Automated batch transfer script with encrypt-transfer-verify-cleanup pipeline |
| Documentation | Demo runner presents the entire pipeline in a step-by-step presentable format |
| Root Cause Analysis | Debugged real technical failures throughout the build (see [Debugging Log](#debugging-log)) |

---

## Architecture

```
HOST (Trading Partner)                      DISTROBOX (Integration Server)
========================                    ================================

~/sftp-demo/edi-samples/                    SFTP Server (port 2222)
  x12/  5x 837P claims                       - Chroot jail: /sftp/sftpuser/
  hl7/  5x ADT admissions                    - Key-based auth (ed25519)
          |                                   - ForceCommand internal-sftp
          v                                   - No shell access
  ~/sftp-outbox/  (staging)                        |
          |                                        v
    PGP encrypt with                         /sftp/sftpuser/uploads/
    server's public key                       - .gpg encrypted files land here
          |                                   - MANIFEST.sha256 for integrity
    SFTP batch transfer ──────────────>            |
    (automated script)                             v
          |                                  GPG decrypt with server's
    Audit log written                        private key
    SHA-256 manifest sent                          |
                                                   v
                                             Python EDI Parser
                                               - X12 837P -> claims data
                                               - HL7 ADT -> admission data
                                                   |
                                                   v
                                             Matplotlib Dashboard
                                               - Charges by drug
                                               - Revenue by payer
                                               - Patients by diagnosis
                                               - Infusion bay schedule
                                               - Claims summary table
                                                   |
                                                   v
    PGP decrypt with            <────────── PGP encrypt with
    partner's private key       SFTP GET    partner's public key
          |
          v
    Dashboard displayed
    inline via Kitty icat
```

---

## Security Layers

| Layer | Implementation | Purpose |
|:--|:--|:--|
| Transport Encryption | SSH/SFTP tunnel | Protects data in transit |
| At-Rest Encryption | PGP/GPG (RSA 4096) | Files encrypted on disk, unreadable without private key |
| Authentication | Ed25519 SSH keypair + ssh-agent | No password-based auth for automation |
| Filesystem Isolation | OpenSSH ChrootDirectory | User jailed to `/sftp/sftpuser/`, can't see rest of system |
| Shell Restriction | ForceCommand internal-sftp + /usr/sbin/nologin | No interactive shell access, SFTP only |
| Integrity Verification | SHA-256 checksums (MANIFEST.sha256) | Detects file corruption or tampering |
| Audit Trail | Timestamped transfer.log | Records every transfer job for compliance review |

---

## EDI Data

### X12 837P Claims (Infusion Therapy Billing)

Simulates claims for five patients receiving biologic infusion drugs:

| Patient | Diagnosis (ICD-10) | Drug (J-Code) | CPT Codes | Payer | Charge |
|:--|:--|:--|:--|:--|--:|
| Maria Santos | Rheumatoid Arthritis (M05.79) | Remicade / J1745 | 96365, 96366 | Aetna | $3,200 |
| James Wilson | Breast Cancer (C50.911) | Herceptin / J9355 | 96413 | UnitedHealthcare | $4,800 |
| Sarah Chen | Crohn's Disease (K50.10) | Entyvio / J3380 | 96365 | BlueCross | $2,100 |
| Robert Jackson | Multiple Sclerosis (G35) | Ocrevus / J2350 | 96365, 96366x3 | Cigna | $6,500 |
| Emily Rodriguez | Rheumatoid Arthritis (M05.79) | Rituxan / J9312 | 96413, 96415 | Aetna | $5,200 |

**Total billed: $21,800**

### HL7 ADT A01 Admissions (Clinical)

Matching patient admissions with infusion bay assignments, attending physicians, drug alerts, and procedure timestamps. Demonstrates the clinical data flow that complements the billing data above.

---

## Project Structure

```
sftp-healthcare-demo/
├── scripts/
│   ├── sftp-transfer.sh        # Automated encrypt + transfer + verify pipeline
│   └── sftp-demo-run.sh        # One-command demo runner (presentation mode)
├── parser/
│   └── process_edi.py          # X12/HL7 parser + dashboard generator
├── edi-samples/
│   ├── x12/                    # 5x X12 837P professional claims
│   │   ├── 837_claim_001.edi
│   │   ├── 837_claim_002.edi
│   │   ├── 837_claim_003.edi
│   │   ├── 837_claim_004.edi
│   │   └── 837_claim_005.edi
│   └── hl7/                    # 5x HL7 ADT A01 admission messages
│       ├── adt_admit_001.hl7
│       ├── adt_admit_002.hl7
│       ├── adt_admit_003.hl7
│       ├── adt_admit_004.hl7
│       └── adt_admit_005.hl7
└── docs/
    └── debugging-log.md        # Real technical issues encountered and resolved
```

---

## Pipeline Steps

The demo runner (`sftp-demo-run.sh`) executes the full pipeline in presentation mode:

1. **Show EDI source files** — 10 healthcare files (5 X12 claims + 5 HL7 admissions) with a peek at raw X12
2. **Stage files in outbox** — Copy EDI files to the transfer staging directory
3. **PGP encrypt & SFTP transfer** — Encrypt each file with the server's public key, generate SHA-256 manifest, batch transfer via SFTP
4. **Server-side integrity verification** — List encrypted files on server, verify checksums
5. **Server-side decrypt & process** — Decrypt with server's private key, parse X12 + HL7, generate dashboard
6. **Display dashboard** — Infusion therapy claims visualization rendered inline (Kitty icat)
7. **Encrypted return transfer** — Dashboard encrypted with partner's public key, pulled back via SFTP, decrypted locally

---

## Debugging Log

Real technical issues encountered and resolved during the build. These demonstrate root cause analysis and troubleshooting ability.

### 1. Shared Home Directory Conflict
**Symptom:** First distrobox attempt failed — SFTP server couldn't authenticate users properly.
**Root Cause:** Distrobox shares the host's home directory by default. When sshd started inside the container, it read the host's SSH configs and keys, creating a muddled auth context.
**Fix:** Created the distrobox with `--home ~/distrobox-homes/sftp-server` to give the container its own isolated home directory.

### 2. Btrfs Inode Overflow in Container
**Symptom:** `distrobox enter` failed during skel setup with `Value too large for defined data type`.
**Root Cause:** The host's home directory sits on an encrypted LUKS btrfs loop device. Btrfs can generate inode numbers that exceed what some 32-bit `stat` structures can handle.
**Fix:** Pre-created the skel files (`.bashrc`, `.bash_profile`, `.bash_logout`) from the host side before entering the distrobox.

### 3. Host sshd Already Running on Port 22
**Symptom:** Potential port conflict; `sshd` was active and enabled on the host.
**Root Cause:** The OS base image ships with `openssh-server` installed and `sshd` enabled by default.
**Fix:** Disabled host sshd and used port 2222 for the container's sshd.

### 4. PAM Rejecting nologin Shell
**Symptom:** Password authentication failed for `sftpuser` despite correct password.
**Root Cause:** PAM's `pam_shells` module checks the user's shell against `/etc/shells` during authentication — before SSH's `ForceCommand` directive takes effect. Since `/usr/sbin/nologin` wasn't listed, PAM rejected the login.
**Fix:** Added `/usr/sbin/nologin` to `/etc/shells` inside the container.

### 5. AuthorizedKeysFile First-Match-Wins
**Symptom:** Key-based authentication failed — server rejected the offered public key.
**Root Cause:** Two `AuthorizedKeysFile` directives existed in `sshd_config`. OpenSSH uses first-match-wins for global directives, so the default path won.
**Fix:** Commented out the default directive and moved the custom `AuthorizedKeysFile` inside the `Match User sftpuser` block.

### 6. Kitty Terminal Type Not Recognized in Container
**Symptom:** `nano` and `vi` failed with `Error opening terminal: xterm-kitty`.
**Root Cause:** Kitty terminal sets `$TERM=xterm-kitty` which requires Kitty's own terminfo database. Minimal containers don't ship this.
**Fix:** `export TERM=xterm-256color` inside the container.

### 7. GPG Passphrase Blocking Non-Interactive Decryption
**Symptom:** Demo runner reported successful decryption but Python parser found 0 files.
**Root Cause:** The server's GPG key had a passphrase. When running non-interactively, pinentry couldn't display a prompt. GPG silently failed and the output directory was empty.
**Fix:** Removed the passphrase from the server's GPG key. In production, automated decryption keys are typically passwordless with security enforced through filesystem permissions.

### 8. Host-Side Glob Expansion for Container Paths
**Symptom:** Decrypt step failed with `can't open '/sftp/sftpuser/uploads/*.gpg': No such file or directory`.
**Root Cause:** The glob expanded on the host shell where `/sftp/` doesn't exist, and was passed literally to the container.
**Fix:** Wrapped the entire decrypt loop in a single `bash -c '...'` block inside `distrobox enter` so the glob expands in the container.

---

## Tech Stack

- **SFTP Server:** OpenSSH (containerized in distrobox/podman)
- **Encryption:** GnuPG (RSA 4096 for PGP, Ed25519 for SSH)
- **Automation:** Bash (batch transfer, checksums, audit logging)
- **EDI Parsing:** Python 3 (custom X12 837P + HL7 ADT parser)
- **Visualization:** Matplotlib
- **Container:** Distrobox + Podman (CachyOS v3 image)
- **Host OS:** ZenaOS 43 (Fedora Atomic)
