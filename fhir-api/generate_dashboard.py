"""
FHIR-sourced infusion therapy dashboard generator.

Pulls Claims, Coverage, and Patient data from the FHIR server via REST API,
aggregates by drug, payer, and diagnosis, and renders a matplotlib dashboard.
Mirrors the SFTP demo's dashboard to show data consistency across integration methods.
"""

import json
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from fhir_client import FHIRClient

# Dashboard color palette
BG_COLOR = "#1a1a2e"
PANEL_COLOR = "#16213e"
TEXT_COLOR = "#e0e0e0"
ACCENT_COLORS = ["#e94560", "#0f3460", "#533483", "#00b4d8", "#06d6a0"]
GRID_COLOR = "#2a2a4a"

# J-code → drug display name mapping
DRUG_NAMES = {
    "J1745": "Remicade",
    "J9355": "Herceptin",
    "J3380": "Entyvio",
    "J2350": "Ocrevus",
    "J9312": "Rituxan",
}


def load_resource_ids():
    try:
        with open("created_resource_ids.json") as f:
            return json.load(f)
    except FileNotFoundError:
        print("No resource IDs found. Run seed_resources.py first.")
        sys.exit(1)


def fetch_dashboard_data(client, resource_ids):
    """Pull all Claims and Coverage from the FHIR server, return structured data."""
    claims_data = []

    for i, patient_id in enumerate(resource_ids["Patient"]):
        # Fetch claims for this patient
        bundle = client.search("Claim", {"patient": f"Patient/{patient_id}"})
        for entry in bundle.get("entry", []):
            claim = entry["resource"]

            # Extract diagnosis code
            diag = claim.get("diagnosis", [{}])[0]
            diag_coding = diag.get("diagnosisCodeableConcept", {}).get("coding", [{}])[0]

            # Extract J-code from line items
            drug_code = None
            for item in claim.get("item", []):
                code = item.get("productOrService", {}).get("coding", [{}])[0].get("code", "")
                if code.startswith("J"):
                    drug_code = code
                    break

            # Extract charge
            charge = claim.get("total", {}).get("value", 0)

            claims_data.append({
                "patient_id": patient_id,
                "diagnosis_code": diag_coding.get("code", "N/A"),
                "diagnosis_display": diag_coding.get("display", "N/A"),
                "drug_code": drug_code or "N/A",
                "drug_name": DRUG_NAMES.get(drug_code, drug_code or "N/A"),
                "charge": charge,
            })

    # Fetch coverage/payer data
    payer_data = []
    for patient_id in resource_ids["Patient"]:
        bundle = client.search("Coverage", {"beneficiary": f"Patient/{patient_id}"})
        for entry in bundle.get("entry", []):
            cov = entry["resource"]
            payor = cov.get("payor", [{}])[0].get("display", "Unknown")
            payer_data.append({
                "patient_id": patient_id,
                "payer": payor,
            })

    # Fetch patient names
    patient_names = {}
    for patient_id in resource_ids["Patient"]:
        pt = client.read("Patient", patient_id)
        name = pt.get("name", [{}])[0]
        patient_names[patient_id] = f"{' '.join(name.get('given', []))} {name.get('family', '')}"

    return claims_data, payer_data, patient_names


def generate_dashboard(claims_data, payer_data, patient_names, api_calls, output_path):
    """Render the infusion therapy dashboard from FHIR API data."""
    fig = plt.figure(figsize=(18, 11), facecolor=BG_COLOR)
    fig.suptitle(
        "Infusion Therapy Claims Dashboard — FHIR API Source",
        color=TEXT_COLOR, fontsize=16, fontweight="bold", y=0.97,
    )
    fig.text(
        0.5, 0.94,
        "Data retrieved via FHIR R4 REST API from HAPI test server",
        color="#888888", fontsize=10, ha="center",
    )

    gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3,
                  left=0.06, right=0.97, top=0.90, bottom=0.06)

    # ── Panel 1: Charges by Drug (horizontal bar) ──────────
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor(PANEL_COLOR)

    drug_charges = {}
    for c in claims_data:
        drug_charges[c["drug_name"]] = drug_charges.get(c["drug_name"], 0) + c["charge"]

    drugs = list(drug_charges.keys())
    charges = list(drug_charges.values())
    bars = ax1.barh(drugs, charges, color=ACCENT_COLORS[:len(drugs)], height=0.6)
    ax1.set_title("Charges by Drug", color=TEXT_COLOR, fontsize=11, fontweight="bold")
    ax1.set_xlabel("Charge ($)", color=TEXT_COLOR, fontsize=9)
    ax1.tick_params(colors=TEXT_COLOR, labelsize=8)
    ax1.set_xlim(0, max(charges) * 1.2)
    for bar, val in zip(bars, charges):
        ax1.text(val + 100, bar.get_y() + bar.get_height() / 2,
                 f"${val:,.0f}", va="center", color=TEXT_COLOR, fontsize=8)
    ax1.grid(axis="x", color=GRID_COLOR, linewidth=0.5)

    # ── Panel 2: Revenue by Payer (pie) ────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor(PANEL_COLOR)

    payer_revenue = {}
    payer_map = {p["patient_id"]: p["payer"] for p in payer_data}
    for c in claims_data:
        payer = payer_map.get(c["patient_id"], "Unknown")
        payer_revenue[payer] = payer_revenue.get(payer, 0) + c["charge"]

    payers = list(payer_revenue.keys())
    revenues = list(payer_revenue.values())
    wedges, texts, autotexts = ax2.pie(
        revenues, labels=payers, autopct="%1.0f%%",
        colors=ACCENT_COLORS[:len(payers)],
        textprops={"color": TEXT_COLOR, "fontsize": 8},
        pctdistance=0.75,
    )
    for at in autotexts:
        at.set_fontsize(8)
        at.set_color(TEXT_COLOR)
    ax2.set_title("Revenue by Payer", color=TEXT_COLOR, fontsize=11, fontweight="bold")

    # ── Panel 3: Patients by Diagnosis (vertical bar) ──────
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.set_facecolor(PANEL_COLOR)

    diag_counts = {}
    for c in claims_data:
        label = c["diagnosis_code"]
        diag_counts[label] = diag_counts.get(label, 0) + 1

    diag_labels = list(diag_counts.keys())
    diag_values = list(diag_counts.values())
    ax3.bar(diag_labels, diag_values, color=ACCENT_COLORS[:len(diag_labels)], width=0.5)
    ax3.set_title("Patients by Diagnosis", color=TEXT_COLOR, fontsize=11, fontweight="bold")
    ax3.set_ylabel("Count", color=TEXT_COLOR, fontsize=9)
    ax3.tick_params(colors=TEXT_COLOR, labelsize=8)
    ax3.set_ylim(0, max(diag_values) + 1)
    ax3.grid(axis="y", color=GRID_COLOR, linewidth=0.5)

    # ── Panel 4: Claims Summary Table ──────────────────────
    ax4 = fig.add_subplot(gs[1, 0:2])
    ax4.set_facecolor(PANEL_COLOR)
    ax4.axis("off")
    ax4.set_title("Claims Summary", color=TEXT_COLOR, fontsize=11,
                   fontweight="bold", loc="left", pad=10)

    table_data = []
    for c in claims_data:
        name = patient_names.get(c["patient_id"], "Unknown")
        table_data.append([
            name,
            c["diagnosis_code"],
            c["drug_name"],
            payer_map.get(c["patient_id"], "N/A"),
            f"${c['charge']:,.2f}",
        ])

    # Total row
    total = sum(c["charge"] for c in claims_data)
    table_data.append(["", "", "", "Total", f"${total:,.2f}"])

    table = ax4.table(
        cellText=table_data,
        colLabels=["Patient", "ICD-10", "Drug", "Payer", "Charge"],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)

    for key, cell in table.get_celld().items():
        cell.set_edgecolor(GRID_COLOR)
        if key[0] == 0:
            cell.set_facecolor("#0f3460")
            cell.set_text_props(color=TEXT_COLOR, fontweight="bold")
        elif key[0] == len(table_data):
            cell.set_facecolor("#1a1a3e")
            cell.set_text_props(color="#e94560", fontweight="bold")
        else:
            cell.set_facecolor(PANEL_COLOR)
            cell.set_text_props(color=TEXT_COLOR)

    # ── Panel 5: API Call Stats ────────────────────────────
    ax5 = fig.add_subplot(gs[1, 2])
    ax5.set_facecolor(PANEL_COLOR)
    ax5.axis("off")
    ax5.set_title("API Performance", color=TEXT_COLOR, fontsize=11,
                   fontweight="bold", loc="left", pad=10)

    total_calls = len(api_calls)
    total_time = sum(c["time_ms"] for c in api_calls)
    avg_time = total_time / total_calls if total_calls else 0
    success_count = sum(1 for c in api_calls if 200 <= c["status"] < 300)

    stats_text = (
        f"Total API Calls:  {total_calls}\n"
        f"Success Rate:     {success_count}/{total_calls} ({100 * success_count / total_calls:.0f}%)\n"
        f"Total Time:       {total_time:,.0f}ms\n"
        f"Avg Latency:      {avg_time:,.0f}ms/call\n"
        f"\nEndpoint Breakdown:\n"
    )

    method_counts = {}
    for c in api_calls:
        method_counts[c["method"]] = method_counts.get(c["method"], 0) + 1
    for method, count in sorted(method_counts.items()):
        stats_text += f"  {method:6s}  {count} calls\n"

    ax5.text(0.08, 0.85, stats_text, transform=ax5.transAxes,
             color=TEXT_COLOR, fontsize=9, fontfamily="monospace",
             verticalalignment="top")

    plt.savefig(output_path, dpi=150, facecolor=BG_COLOR)
    plt.close()
    return output_path


def main():
    client = FHIRClient()
    resource_ids = load_resource_ids()

    print("Fetching data from FHIR server...")
    claims_data, payer_data, patient_names = fetch_dashboard_data(client, resource_ids)
    print(f"  Retrieved {len(claims_data)} claims, {len(payer_data)} coverage records")

    output = "fhir_dashboard.png"
    generate_dashboard(claims_data, payer_data, patient_names, client.get_call_summary(), output)
    print(f"  Dashboard saved to {output}")

    # Display inline if running in Kitty
    import shutil
    if shutil.which("kitten"):
        import subprocess
        subprocess.run(["kitten", "icat", output])


if __name__ == "__main__":
    main()
