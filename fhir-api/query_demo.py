"""
FHIR R4 search and query demonstration.

Showcases FHIR search parameters, modifiers, includes, and comparators
against seeded infusion therapy resources. Requires seed_resources.py
to have been run first (reads created_resource_ids.json).
"""

import json
import sys
from fhir_client import FHIRClient

CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def banner(title):
    print(f"\n{CYAN}{'─' * 60}{NC}")
    print(f"{BOLD}  {title}{NC}")
    print(f"{CYAN}{'─' * 60}{NC}")


def show_query(method, path, params=None):
    """Display the FHIR query being executed."""
    param_str = ""
    if params:
        param_str = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    print(f"\n  {DIM}{method} {path}{param_str}{NC}")


def extract_entries(bundle):
    """Safely extract resource entries from a FHIR search Bundle."""
    return [entry["resource"] for entry in bundle.get("entry", [])]


def load_resource_ids():
    """Load the resource IDs created by seed_resources.py."""
    try:
        with open("created_resource_ids.json") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{YELLOW}No resource IDs found. Run seed_resources.py first.{NC}")
        sys.exit(1)


def query_patient_by_name(client):
    """Search for a patient using the FHIR name search parameter."""
    banner("Query 1: Search Patient by Name")
    params = {"name": "Santos", "identifier": "http://itp-demo.example.com/mrn|"}
    show_query("GET", "/Patient", params)

    bundle = client.search("Patient", params)
    patients = extract_entries(bundle)
    print(f"  {GREEN}Found {len(patients)} result(s){NC}")

    for pt in patients:
        name = pt.get("name", [{}])[0]
        given = " ".join(name.get("given", []))
        family = name.get("family", "")
        print(f"    • {given} {family} (ID: {pt['id']})")
        print(f"      Gender: {pt.get('gender', 'N/A')} | DOB: {pt.get('birthDate', 'N/A')}")


def query_claims_by_patient(client, resource_ids):
    """Retrieve all claims for a specific patient."""
    banner("Query 2: Claims by Patient")
    patient_id = resource_ids["Patient"][0]  # Maria Santos
    params = {"patient": f"Patient/{patient_id}"}
    show_query("GET", "/Claim", params)

    bundle = client.search("Claim", params)
    claims = extract_entries(bundle)
    print(f"  {GREEN}Found {len(claims)} claim(s) for Patient/{patient_id}{NC}")

    for claim in claims:
        total = claim.get("total", {})
        diag = claim.get("diagnosis", [{}])[0]
        diag_code = diag.get("diagnosisCodeableConcept", {}).get("coding", [{}])[0]
        print(f"    • Claim/{claim['id']}")
        print(f"      Diagnosis: {diag_code.get('code', 'N/A')} — {diag_code.get('display', 'N/A')}")
        print(f"      Total: ${total.get('value', 0):,.2f}")


def query_coverage_by_patient(client, resource_ids):
    """Look up insurance coverage for a patient — the eligibility check."""
    banner("Query 3: Eligibility Check (Coverage by Patient)")
    patient_id = resource_ids["Patient"][2]  # Sarah Chen
    params = {"beneficiary": f"Patient/{patient_id}"}
    show_query("GET", "/Coverage", params)

    bundle = client.search("Coverage", params)
    coverages = extract_entries(bundle)
    print(f"  {GREEN}Found {len(coverages)} coverage(s) for Patient/{patient_id}{NC}")

    for cov in coverages:
        payor = cov.get("payor", [{}])[0].get("display", "Unknown")
        period = cov.get("period", {})
        status = cov.get("status", "unknown")
        classes = cov.get("class", [{}])
        group = classes[0].get("value", "N/A") if classes else "N/A"
        print(f"    • Coverage/{cov['id']}")
        print(f"      Payor: {payor} | Status: {status}")
        print(f"      Period: {period.get('start', '?')} → {period.get('end', '?')}")
        print(f"      Group: {group}")


def query_claims_with_include(client, resource_ids):
    """Use _include to fetch Claims with their linked Patient in one request."""
    banner("Query 4: Claims with _include (Patient)")
    patient_id = resource_ids["Patient"][3]  # Robert Jackson
    params = {
        "patient": f"Patient/{patient_id}",
        "_include": "Claim:patient",
    }
    show_query("GET", "/Claim", params)

    bundle = client.search("Claim", params)
    entries = extract_entries(bundle)

    claims = [e for e in entries if e["resourceType"] == "Claim"]
    patients = [e for e in entries if e["resourceType"] == "Patient"]

    print(f"  {GREEN}Single request returned {len(claims)} Claim(s) + {len(patients)} Patient(s){NC}")
    print(f"  {DIM}_include avoids N+1 queries by embedding referenced resources{NC}")

    for pt in patients:
        name = pt.get("name", [{}])[0]
        print(f"    Patient: {' '.join(name.get('given', []))} {name.get('family', '')}")
    for claim in claims:
        total = claim.get("total", {}).get("value", 0)
        print(f"    Claim/{claim['id']}: ${total:,.2f}")


def query_all_claims_summary(client, resource_ids):
    """Pull all demo claims and summarize — aggregate reporting via API."""
    banner("Query 5: All Claims Summary (Aggregate View)")

    # Search for claims from our org by collecting all patient claims
    all_claims = []
    for patient_id in resource_ids["Patient"]:
        bundle = client.search("Claim", {"patient": f"Patient/{patient_id}"})
        all_claims.extend(extract_entries(bundle))

    show_query("GET", "/Claim", {"patient": "Patient/{id} × 5 patients"})
    print(f"  {GREEN}Retrieved {len(all_claims)} total claims{NC}\n")

    # Summary table
    total_charged = 0
    print(f"  {'Patient':<20} {'Diagnosis':<10} {'Drug':<8} {'Charge':>10}")
    print(f"  {'─' * 20} {'─' * 10} {'─' * 8} {'─' * 10}")

    for claim in all_claims:
        # Extract patient name from reference
        patient_ref = claim.get("patient", {}).get("reference", "")

        # Extract diagnosis
        diag = claim.get("diagnosis", [{}])[0]
        diag_code = diag.get("diagnosisCodeableConcept", {}).get("coding", [{}])[0].get("code", "N/A")

        # Find J-code in line items
        drug_code = "N/A"
        for item in claim.get("item", []):
            code = item.get("productOrService", {}).get("coding", [{}])[0].get("code", "")
            if code.startswith("J"):
                drug_code = code
                break

        charge = claim.get("total", {}).get("value", 0)
        total_charged += charge

        print(f"  {patient_ref:<20} {diag_code:<10} {drug_code:<8} ${charge:>9,.2f}")

    print(f"  {'─' * 20} {'─' * 10} {'─' * 8} {'─' * 10}")
    print(f"  {BOLD}{'Total':<40} ${total_charged:>9,.2f}{NC}")


def query_api_call_summary(client):
    """Display a summary of all API calls made during the demo."""
    banner("API Call Summary")
    calls = client.get_call_summary()
    total_time = sum(c["time_ms"] for c in calls)

    print(f"\n  {'Method':<8} {'Endpoint':<35} {'Status':>6} {'Time':>8}")
    print(f"  {'─' * 8} {'─' * 35} {'─' * 6} {'─' * 8}")

    for call in calls:
        endpoint = call["url"][:35]
        print(f"  {call['method']:<8} {endpoint:<35} {call['status']:>6} {call['time_ms']:>6}ms")

    print(f"\n  {BOLD}{len(calls)} API calls | {total_time:,.0f}ms total | avg {total_time / len(calls):,.0f}ms/call{NC}")


def main():
    client = FHIRClient()
    resource_ids = load_resource_ids()

    print(f"{BOLD}FHIR Search & Query Demo — Infusion Therapy Partners{NC}")
    print(f"{DIM}Target: {client.base_url}{NC}")

    query_patient_by_name(client)
    query_claims_by_patient(client, resource_ids)
    query_coverage_by_patient(client, resource_ids)
    query_claims_with_include(client, resource_ids)
    query_all_claims_summary(client, resource_ids)
    query_api_call_summary(client)


if __name__ == "__main__":
    main()
