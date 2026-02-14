"""
FHIR R4 resource seeder for infusion therapy demo environment.

Creates a complete set of interlinked healthcare resources on a FHIR server:
Organization → Practitioners → Patients → Coverage → Claims.

Resources mirror the X12 837P and HL7 ADT data from the SFTP demo,
demonstrating API-based integration of the same clinical dataset.
"""

import json
import sys
from fhir_client import FHIRClient

# ── Color output helpers ────────────────────────────────────

CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def success(msg):
    print(f"  {GREEN}✓{NC} {msg}")


def info(msg):
    print(f"  {DIM}{msg}{NC}")


# ── Resource definitions ────────────────────────────────────
# All clinical data matches the X12 837P claims and HL7 ADT admissions
# from the SFTP demo (same patients, diagnoses, drugs, payers).

ORGANIZATION = {
    "resourceType": "Organization",
    "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "1234567890"}],
    "active": True,
    "name": "Infusion Therapy Partners LLC",
    "type": [
        {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                    "code": "prov",
                    "display": "Healthcare Provider",
                }
            ]
        }
    ],
    "telecom": [{"system": "phone", "value": "512-555-0100"}],
    "address": [
        {
            "line": ["456 Medical Center Blvd", "Suite 200"],
            "city": "Austin",
            "state": "TX",
            "postalCode": "78701",
        }
    ],
}

PRACTITIONERS = [
    {
        "resourceType": "Practitioner",
        "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "1122334455"}],
        "name": [{"family": "Rivera", "given": ["Ana"], "prefix": ["Dr."]}],
        "qualification": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0360",
                            "code": "MD",
                        }
                    ]
                }
            }
        ],
    },
    {
        "resourceType": "Practitioner",
        "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "2233445566"}],
        "name": [{"family": "Park", "given": ["David"], "prefix": ["Dr."]}],
        "qualification": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0360",
                            "code": "MD",
                        }
                    ]
                }
            }
        ],
    },
    {
        "resourceType": "Practitioner",
        "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "3344556677"}],
        "name": [{"family": "Goldstein", "given": ["Rachel"], "prefix": ["Dr."]}],
        "qualification": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0360",
                            "code": "MD",
                        }
                    ]
                }
            }
        ],
    },
    {
        "resourceType": "Practitioner",
        "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "4455667788"}],
        "name": [{"family": "Okafor", "given": ["Chidi"], "prefix": ["Dr."]}],
        "qualification": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0360",
                            "code": "MD",
                        }
                    ]
                }
            }
        ],
    },
    {
        "resourceType": "Practitioner",
        "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "5566778899"}],
        "name": [{"family": "Chen", "given": ["Lisa"], "prefix": ["Dr."]}],
        "qualification": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0360",
                            "code": "MD",
                        }
                    ]
                }
            }
        ],
    },
]

# Patient definitions — each maps to one X12 837P claim and one HL7 ADT admission
PATIENTS = [
    {
        "resourceType": "Patient",
        "identifier": [{"system": "http://itp-demo.example.com/mrn", "value": "ITP-001"}],
        "name": [{"family": "Santos", "given": ["Maria"]}],
        "gender": "female",
        "birthDate": "1978-03-15",
        "address": [{"city": "Austin", "state": "TX", "postalCode": "78701"}],
    },
    {
        "resourceType": "Patient",
        "identifier": [{"system": "http://itp-demo.example.com/mrn", "value": "ITP-002"}],
        "name": [{"family": "Wilson", "given": ["James"]}],
        "gender": "male",
        "birthDate": "1965-07-22",
        "address": [{"city": "Austin", "state": "TX", "postalCode": "78702"}],
    },
    {
        "resourceType": "Patient",
        "identifier": [{"system": "http://itp-demo.example.com/mrn", "value": "ITP-003"}],
        "name": [{"family": "Chen", "given": ["Sarah"]}],
        "gender": "female",
        "birthDate": "1990-11-08",
        "address": [{"city": "Austin", "state": "TX", "postalCode": "78703"}],
    },
    {
        "resourceType": "Patient",
        "identifier": [{"system": "http://itp-demo.example.com/mrn", "value": "ITP-004"}],
        "name": [{"family": "Jackson", "given": ["Robert"]}],
        "gender": "male",
        "birthDate": "1972-01-30",
        "address": [{"city": "Austin", "state": "TX", "postalCode": "78704"}],
    },
    {
        "resourceType": "Patient",
        "identifier": [{"system": "http://itp-demo.example.com/mrn", "value": "ITP-005"}],
        "name": [{"family": "Rodriguez", "given": ["Emily"]}],
        "gender": "female",
        "birthDate": "1985-09-12",
        "address": [{"city": "Austin", "state": "TX", "postalCode": "78705"}],
    },
]

# Payer orgs — referenced by Coverage resources
PAYERS = [
    {"name": "Aetna", "identifier": "52415"},
    {"name": "UnitedHealthcare", "identifier": "87726"},
    {"name": "BlueCross BlueShield", "identifier": "00312"},
    {"name": "Cigna", "identifier": "62308"},
    {"name": "Aetna", "identifier": "52415"},  # Rodriguez also on Aetna
]

# Clinical data per patient — maps diagnosis, drug, CPT codes, and charges
# directly from the X12 837P claims
CLINICAL_DATA = [
    {
        "diagnosis_code": "M05.79",
        "diagnosis_display": "Rheumatoid arthritis",
        "drug_code": "J1745",
        "drug_display": "Infliximab (Remicade) injection",
        "cpt_codes": ["96365", "96366"],
        "charge": 3200.00,
    },
    {
        "diagnosis_code": "C50.911",
        "diagnosis_display": "Malignant neoplasm of breast",
        "drug_code": "J9355",
        "drug_display": "Trastuzumab (Herceptin) injection",
        "cpt_codes": ["96413"],
        "charge": 4800.00,
    },
    {
        "diagnosis_code": "K50.10",
        "diagnosis_display": "Crohn's disease of large intestine",
        "drug_code": "J3380",
        "drug_display": "Vedolizumab (Entyvio) injection",
        "cpt_codes": ["96365"],
        "charge": 2100.00,
    },
    {
        "diagnosis_code": "G35",
        "diagnosis_display": "Multiple sclerosis",
        "drug_code": "J2350",
        "drug_display": "Ocrelizumab (Ocrevus) injection",
        "cpt_codes": ["96365", "96366", "96366", "96366"],
        "charge": 6500.00,
    },
    {
        "diagnosis_code": "M05.79",
        "diagnosis_display": "Rheumatoid arthritis",
        "drug_code": "J9312",
        "drug_display": "Rituximab (Rituxan) injection",
        "cpt_codes": ["96413", "96415"],
        "charge": 5200.00,
    },
]


def build_coverage(patient_ref, payer, index):
    """Build a Coverage resource linking a patient to their insurance plan."""
    return {
        "resourceType": "Coverage",
        "status": "active",
        "subscriber": {"reference": patient_ref},
        "beneficiary": {"reference": patient_ref},
        "payor": [{"display": payer["name"]}],
        "type": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                    "code": "HIP",
                    "display": "health insurance plan policy",
                }
            ]
        },
        "period": {"start": "2025-01-01", "end": "2025-12-31"},
        "class": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/coverage-class",
                            "code": "group",
                        }
                    ]
                },
                "value": f"GRP-{payer['identifier']}",
                "name": f"{payer['name']} Employer Group",
            }
        ],
    }


def build_claim(patient_ref, org_ref, practitioner_ref, coverage_ref, clinical, index):
    """Build a Claim resource with diagnosis and infusion line items."""
    # Line items — one per CPT code in the procedure
    items = []
    for i, cpt in enumerate(clinical["cpt_codes"], start=1):
        items.append(
            {
                "sequence": i,
                "productOrService": {
                    "coding": [
                        {
                            "system": "http://www.ama-assn.org/go/cpt",
                            "code": cpt,
                        }
                    ]
                },
                "unitPrice": {
                    "value": round(clinical["charge"] / len(clinical["cpt_codes"]), 2),
                    "currency": "USD",
                },
                "quantity": {"value": 1},
            }
        )

    # Add the drug as a separate line item (J-code)
    items.append(
        {
            "sequence": len(items) + 1,
            "productOrService": {
                "coding": [
                    {
                        "system": "http://www.ama-assn.org/go/cpt",
                        "code": clinical["drug_code"],
                        "display": clinical["drug_display"],
                    }
                ]
            },
            "unitPrice": {"value": 0.00, "currency": "USD"},
            "quantity": {"value": 1},
        }
    )

    return {
        "resourceType": "Claim",
        "status": "active",
        "type": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                    "code": "professional",
                    "display": "Professional",
                }
            ]
        },
        "use": "claim",
        "patient": {"reference": patient_ref},
        "created": "2025-02-14",
        "provider": {"reference": org_ref},
        "priority": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/processpriority",
                    "code": "normal",
                }
            ]
        },
        "insurance": [
            {
                "sequence": 1,
                "focal": True,
                "coverage": {"reference": coverage_ref},
            }
        ],
        "diagnosis": [
            {
                "sequence": 1,
                "diagnosisCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://hl7.org/fhir/sid/icd-10-cm",
                            "code": clinical["diagnosis_code"],
                            "display": clinical["diagnosis_display"],
                        }
                    ]
                },
            }
        ],
        "item": items,
        "total": {"value": clinical["charge"], "currency": "USD"},
    }


def seed_all(client):
    """
    Create all demo resources on the FHIR server in dependency order.

    Returns a dict of resource type → list of server-assigned IDs
    for downstream use and cleanup.
    """
    created_ids = {
        "Organization": [],
        "Practitioner": [],
        "Patient": [],
        "Coverage": [],
        "Claim": [],
    }

    # 1. Organization
    print(f"\n{CYAN}Creating Organization...{NC}")
    org = client.create_or_find(
        "Organization", ORGANIZATION,
        {"identifier": "http://hl7.org/fhir/sid/us-npi|1234567890"},
    )
    org_ref = f"Organization/{org['id']}"
    created_ids["Organization"].append(org["id"])
    tag = "(existing)" if org.get("_reused") else "(new)"
    success(f"Infusion Therapy Partners LLC → {org['id']} {tag}")

    # 2. Practitioners
    print(f"\n{CYAN}Creating Practitioners...{NC}")
    practitioner_refs = []
    for prac_data in PRACTITIONERS:
        npi = prac_data["identifier"][0]["value"]
        prac = client.create_or_find(
            "Practitioner", prac_data,
            {"identifier": f"http://hl7.org/fhir/sid/us-npi|{npi}"},
        )
        prac_ref = f"Practitioner/{prac['id']}"
        practitioner_refs.append(prac_ref)
        created_ids["Practitioner"].append(prac["id"])
        name = prac_data["name"][0]
        tag = "(existing)" if prac.get("_reused") else "(new)"
        success(f"Dr. {name['family']} → {prac['id']} {tag}")

    # 3. Patients
    print(f"\n{CYAN}Creating Patients...{NC}")
    patient_refs = []
    for pt_data in PATIENTS:
        mrn = pt_data["identifier"][0]["value"]
        pt = client.create_or_find(
            "Patient", pt_data,
            {"identifier": f"http://itp-demo.example.com/mrn|{mrn}"},
        )
        pt_ref = f"Patient/{pt['id']}"
        patient_refs.append(pt_ref)
        created_ids["Patient"].append(pt["id"])
        name = pt_data["name"][0]
        tag = "(existing)" if pt.get("_reused") else "(new)"
        success(f"{name['given'][0]} {name['family']} (MRN: {mrn}) → {pt['id']} {tag}")

    # 4. Coverage (depends on Patients)
    print(f"\n{CYAN}Creating Coverage resources...{NC}")
    coverage_refs = []
    for i, (pt_ref, payer) in enumerate(zip(patient_refs, PAYERS)):
        cov_data = build_coverage(pt_ref, payer, i)
        cov = client.create_or_find(
            "Coverage", cov_data,
            {"beneficiary": pt_ref, "payor": payer["name"]},
        )
        cov_ref = f"Coverage/{cov['id']}"
        coverage_refs.append(cov_ref)
        created_ids["Coverage"].append(cov["id"])
        pt_name = PATIENTS[i]["name"][0]
        tag = "(existing)" if cov.get("_reused") else "(new)"
        success(f"{pt_name['given'][0]} {pt_name['family']} → {payer['name']} → {cov['id']} {tag}")

    # 5. Claims (depends on Patients, Organization, Practitioners, Coverage)
    print(f"\n{CYAN}Creating Claims...{NC}")
    for i in range(len(PATIENTS)):
        claim_data = build_claim(
            patient_refs[i],
            org_ref,
            practitioner_refs[i],
            coverage_refs[i],
            CLINICAL_DATA[i],
            i,
        )
        claim = client.create_or_find(
            "Claim", claim_data,
            {"patient": patient_refs[i], "provider": org_ref},
        )
        created_ids["Claim"].append(claim["id"])
        pt_name = PATIENTS[i]["name"][0]
        clinical = CLINICAL_DATA[i]
        tag = "(existing)" if claim.get("_reused") else "(new)"
        success(
            f"{pt_name['given'][0]} {pt_name['family']} — "
            f"{clinical['drug_display'].split('(')[1].split(')')[0]} "
            f"${clinical['charge']:,.2f} → {claim['id']} {tag}"
        )

    total = sum(len(ids) for ids in created_ids.values())
    print(f"\n{GREEN}{BOLD}Seeded {total} resources successfully.{NC}")
    return created_ids


def cleanup(client, created_ids):
    """Delete all resources created during seeding (reverse dependency order)."""
    print(f"\n{YELLOW}Cleaning up resources...{NC}")
    # Delete in reverse order to avoid reference integrity issues
    for resource_type in ["Claim", "Coverage", "Patient", "Practitioner", "Organization"]:
        for rid in created_ids.get(resource_type, []):
            try:
                client.delete(resource_type, rid)
                info(f"Deleted {resource_type}/{rid}")
            except Exception as e:
                info(f"Skipped {resource_type}/{rid}: {e}")
    print(f"  {GREEN}✓{NC} Cleanup complete")


def save_ids(created_ids, filepath="created_resource_ids.json"):
    """Persist created resource IDs to disk for use by other demo scripts."""
    with open(filepath, "w") as f:
        json.dump(created_ids, f, indent=2)
    info(f"Resource IDs saved to {filepath}")


if __name__ == "__main__":
    client = FHIRClient()

    if "--cleanup-only" in sys.argv:
        try:
            with open("created_resource_ids.json") as f:
                ids = json.load(f)
            cleanup(client, ids)
        except FileNotFoundError:
            print(f"{RED}No resource ID file found. Nothing to clean up.{NC}")
        sys.exit(0)

    print(f"{BOLD}FHIR Resource Seeder — Infusion Therapy Partners{NC}")
    print(f"{DIM}Target: {client.base_url}{NC}")

    created_ids = seed_all(client)
    save_ids(created_ids)

    print(f"\n{DIM}Run with --cleanup-only to delete these resources.{NC}")
