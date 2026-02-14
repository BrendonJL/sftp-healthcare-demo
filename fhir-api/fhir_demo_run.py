#!/usr/bin/env python3
"""
FHIR API Healthcare Integration Demo — Full Pipeline Runner.

Walks through the complete FHIR integration lifecycle in presentation mode:
connectivity check → resource seeding → search queries → dashboard → cleanup.
"""

import sys
import shutil
import subprocess
from fhir_client import FHIRClient
from seed_resources import seed_all, cleanup, save_ids, PATIENTS, CLINICAL_DATA, PAYERS
from query_demo import (
    query_patient_by_name,
    query_claims_by_patient,
    query_coverage_by_patient,
    query_claims_with_include,
    query_all_claims_summary,
    load_resource_ids,
)
from generate_dashboard import fetch_dashboard_data, generate_dashboard
import requests

CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def banner(title):
    print(f"\n{CYAN}{'═' * 60}{NC}")
    print(f"{BOLD}  {title}{NC}")
    print(f"{CYAN}{'═' * 60}{NC}\n")


def pause():
    print(f"\n{DIM}  Press Enter to continue...{NC}")
    input()


# ── Pre-flight ──────────────────────────────────────────────

banner("FHIR API Healthcare Integration Demo")
print(f"  {BOLD}Infusion Therapy Partners LLC{NC}")
print(f"  RESTful FHIR R4 Integration Pipeline\n")
print(f"  {DIM}Components:{NC}")
print(f"    • FHIR R4 client with request logging")
print(f"    • Patient, Practitioner, Coverage, Claim resources")
print(f"    • Idempotent seeding with duplicate detection")
print(f"    • FHIR search queries (name, reference, _include)")
print(f"    • API-sourced matplotlib dashboard")
print(f"    • Full resource cleanup")

client = FHIRClient()

# Connectivity check
print(f"\n  {DIM}Verifying FHIR server connectivity...{NC}")
url = f"{client.base_url}/metadata"
response = requests.get(url, headers={"Accept": "application/fhir+json"})
if response.status_code == 200:
    meta = response.json()
    server_name = meta.get("implementation", {}).get("description", "FHIR Server")
    fhir_version = meta.get("fhirVersion", "Unknown")
    print(f"  {GREEN}✓ Connected to {server_name}{NC}")
    print(f"  {GREEN}✓ FHIR version: {fhir_version}{NC}")
else:
    print(f"  {RED}✗ Connection failed ({response.status_code}){NC}")
    sys.exit(1)

pause()

# ── Step 1: Seed Resources ─────────────────────────────────

banner("STEP 1: Create FHIR Resources")
print(f"  Creating resources in dependency order:")
print(f"  Organization → Practitioners → Patients → Coverage → Claims\n")

created_ids = seed_all(client)
save_ids(created_ids)

total = sum(len(ids) for ids in created_ids.values())
print(f"\n  {BOLD}{total} resources live on the FHIR server{NC}")

pause()

# ── Step 2: Search Queries ──────────────────────────────────

banner("STEP 2: FHIR Search Queries")
print(f"  Demonstrating FHIR search parameters, references, and _include\n")

resource_ids = load_resource_ids()
query_patient_by_name(client)
query_claims_by_patient(client, resource_ids)
query_coverage_by_patient(client, resource_ids)
query_claims_with_include(client, resource_ids)
query_all_claims_summary(client, resource_ids)

pause()

# ── Step 3: Generate Dashboard ──────────────────────────────

banner("STEP 3: API-Sourced Dashboard")
print(f"  Fetching data from FHIR server and rendering visualization...\n")

claims_data, payer_data, patient_names = fetch_dashboard_data(client, resource_ids)
print(f"  Retrieved {len(claims_data)} claims, {len(payer_data)} coverage records")

output = "fhir_dashboard.png"
generate_dashboard(claims_data, payer_data, patient_names, client.get_call_summary(), output)
print(f"  {GREEN}✓ Dashboard saved to {output}{NC}")

if shutil.which("kitten"):
    print()
    subprocess.run(["kitten", "icat", output])

pause()

# ── Step 4: Cleanup ─────────────────────────────────────────

banner("STEP 4: Resource Cleanup")
print(f"  Removing all demo resources from the FHIR server...\n")

cleanup(client, created_ids)

pause()

# ── Summary ─────────────────────────────────────────────────

banner("Pipeline Complete")
print(f"  {BOLD}What just happened:{NC}\n")
print(f"  1. {DIM}Verified FHIR server connectivity (CapabilityStatement){NC}")
print(f"  2. {DIM}Created {total} interlinked healthcare resources via REST API{NC}")
print(f"  3. {DIM}Searched by patient name, diagnosis, coverage, and references{NC}")
print(f"  4. {DIM}Used _include to eliminate N+1 query overhead{NC}")
print(f"  5. {DIM}Generated claims dashboard from live API data{NC}")
print(f"  6. {DIM}Cleaned up all resources from the test server{NC}")

print(f"\n  {BOLD}FHIR resources used:{NC}")
print(f"    Patient       — member demographics and identifiers")
print(f"    Practitioner  — attending physicians with NPI")
print(f"    Organization  — provider facility")
print(f"    Coverage      — insurance eligibility (payer, plan, period)")
print(f"    Claim         — professional claims with ICD-10, CPT, J-codes")

# API performance summary
calls = client.get_call_summary()
total_time = sum(c["time_ms"] for c in calls)
avg_time = total_time / len(calls) if calls else 0
success_count = sum(1 for c in calls if 200 <= c["status"] < 300)

print(f"\n  {BOLD}API performance:{NC}")
print(f"    {len(calls)} total calls | {success_count} successful ({100 * success_count / len(calls):.0f}%)")
print(f"    {total_time:,.0f}ms total | {avg_time:,.0f}ms avg latency")

print(f"\n{CYAN}{'═' * 60}{NC}")
