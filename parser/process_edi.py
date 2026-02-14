#!/usr/bin/env python3
"""
EDI Processing Pipeline — Infusion Therapy Partners
Parses X12 837P claims and HL7 ADT admissions, generates summary visualization.
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless rendering
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.ticker as mticker


# ── X12 837P Parser ──────────────────────────────────────────────

DRUG_CODES = {
    "J1745": "Remicade (infliximab)",
    "J9355": "Herceptin (trastuzumab)",
    "J3380": "Entyvio (vedolizumab)",
    "J2350": "Ocrevus (ocrelizumab)",
    "J9312": "Rituxan (rituximab)",
}

CPT_DESCRIPTIONS = {
    "96365": "IV Infusion, 1st Hour",
    "96366": "IV Infusion, Addtl Hour",
    "96413": "Chemo IV Infusion, 1st Hour",
    "96415": "Chemo IV Infusion, Addtl Hour",
}

ICD10_DESCRIPTIONS = {
    "M0579": "Rheumatoid Arthritis",
    "C50911": "Breast Cancer",
    "K5010": "Crohn's Disease",
    "G35": "Multiple Sclerosis",
}


def parse_x12_837(filepath):
    """Parse an X12 837P claim file and extract structured data."""
    with open(filepath) as f:
        content = f.read()

    segments = [s.strip() for s in content.replace("\n", "").split("~") if s.strip()]
    claim = {
        "file": os.path.basename(filepath),
        "services": [],
        "diagnoses": [],
    }

    for seg in segments:
        elements = seg.split("*")
        seg_id = elements[0]

        if seg_id == "NM1" and len(elements) > 8:
            qualifier = elements[1]
            if qualifier == "IL":  # Subscriber/patient
                claim["patient_last"] = elements[3]
                claim["patient_first"] = elements[4]
                claim["member_id"] = elements[9] if len(elements) > 9 else ""
            elif qualifier == "PR":  # Payer
                claim["payer"] = elements[3]

        elif seg_id == "DMG" and len(elements) > 3:
            claim["dob"] = elements[2]
            claim["sex"] = elements[3]

        elif seg_id == "CLM" and len(elements) > 2:
            claim["claim_id"] = elements[1]
            claim["total_charge"] = float(elements[2])

        elif seg_id == "HI" and len(elements) > 1:
            for el in elements[1:]:
                parts = el.split(":")
                if len(parts) >= 2:
                    code = parts[1].replace(".", "")
                    desc = ICD10_DESCRIPTIONS.get(code, code)
                    claim["diagnoses"].append({"code": parts[1], "description": desc})

        elif seg_id == "SV1" and len(elements) > 2:
            svc_parts = elements[1].split(":")
            cpt = svc_parts[1] if len(svc_parts) > 1 else ""
            charge = float(elements[2])
            units = int(elements[4]) if len(elements) > 4 else 1
            is_drug = cpt.startswith("J")
            claim["services"].append({
                "cpt": cpt,
                "description": DRUG_CODES.get(cpt, CPT_DESCRIPTIONS.get(cpt, cpt)),
                "charge": charge,
                "units": units,
                "is_drug": is_drug,
            })

    # Derive drug name from J-code service line
    for svc in claim["services"]:
        if svc["is_drug"]:
            claim["drug"] = svc["description"]
            break

    claim["patient"] = f"{claim.get('patient_first', '')} {claim.get('patient_last', '')}"
    return claim


# ── HL7 ADT Parser ──────────────────────────────────────────────

def parse_hl7_adt(filepath):
    """Parse an HL7 v2.x ADT message and extract structured data."""
    with open(filepath) as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]

    admission = {"file": os.path.basename(filepath), "diagnoses": [], "procedures": []}

    for line in lines:
        fields = line.split("|")
        seg_id = fields[0]

        if seg_id == "MSH":
            admission["sending_app"] = fields[2] if len(fields) > 2 else ""
            admission["message_time"] = fields[6] if len(fields) > 6 else ""
            admission["message_type"] = fields[8] if len(fields) > 8 else ""

        elif seg_id == "PID":
            name_parts = fields[5].split("^") if len(fields) > 5 else []
            admission["patient_last"] = name_parts[0] if name_parts else ""
            admission["patient_first"] = name_parts[1] if len(name_parts) > 1 else ""
            admission["patient"] = f"{admission['patient_first']} {admission['patient_last']}"
            admission["dob"] = fields[7] if len(fields) > 7 else ""
            admission["sex"] = fields[8] if len(fields) > 8 else ""
            # Extract address
            addr_parts = fields[11].split("^") if len(fields) > 11 else []
            admission["city"] = addr_parts[2] if len(addr_parts) > 2 else ""
            admission["state"] = addr_parts[3] if len(addr_parts) > 3 else ""

        elif seg_id == "PV1":
            admission["patient_class"] = fields[2] if len(fields) > 2 else ""
            location_parts = fields[3].split("^") if len(fields) > 3 else []
            admission["location"] = location_parts[1] if len(location_parts) > 1 else ""
            doc_parts = fields[7].split("^") if len(fields) > 7 else []
            admission["attending_physician"] = (
                f"Dr. {doc_parts[1]} {doc_parts[2]}" if len(doc_parts) > 2 else ""
            )

        elif seg_id == "DG1":
            diag_parts = fields[3].split("^") if len(fields) > 3 else []
            admission["diagnoses"].append({
                "code": diag_parts[0] if diag_parts else "",
                "description": diag_parts[1] if len(diag_parts) > 1 else "",
            })

        elif seg_id == "IN1":
            admission["payer"] = fields[4] if len(fields) > 4 else ""
            admission["group_number"] = fields[8] if len(fields) > 8 else ""

        elif seg_id == "AL1":
            drug_parts = fields[3].split("^") if len(fields) > 3 else []
            admission["drug_code"] = drug_parts[0] if drug_parts else ""
            admission["drug_name"] = DRUG_CODES.get(
                drug_parts[0], drug_parts[1] if len(drug_parts) > 1 else ""
            )
            admission["alert_severity"] = fields[4] if len(fields) > 4 else ""
            admission["alert_note"] = fields[5] if len(fields) > 5 else ""

        elif seg_id == "PR1":
            proc_parts = fields[3].split("^") if len(fields) > 3 else []
            admission["procedures"].append({
                "cpt": proc_parts[0] if proc_parts else "",
                "description": proc_parts[1] if len(proc_parts) > 1 else "",
                "detail": fields[4] if len(fields) > 4 else "",
            })

    return admission


# ── Visualization ────────────────────────────────────────────────

def build_dashboard(claims, admissions, output_path):
    """Generate a multi-panel dashboard from parsed EDI data."""

    fig = plt.figure(figsize=(20, 14), facecolor="#1a1a2e")
    fig.suptitle(
        "Infusion Therapy Partners — Daily Claims & Admissions Dashboard",
        fontsize=18, fontweight="bold", color="white", y=0.98,
    )
    fig.text(
        0.5, 0.955,
        f"Date: {datetime.now().strftime('%B %d, %Y')}  |  "
        f"Claims: {len(claims)}  |  Admissions: {len(admissions)}  |  "
        f"Total Billed: ${sum(c['total_charge'] for c in claims):,.0f}",
        ha="center", fontsize=12, color="#aaaaaa",
    )

    gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3,
                  top=0.92, bottom=0.06, left=0.06, right=0.97)

    colors = ["#e94560", "#0f3460", "#16213e", "#533483", "#e07c24"]
    accent = "#e94560"

    # ── Panel 1: Charges by Drug ──
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor("#16213e")
    drugs = [c.get("drug", "Unknown") for c in claims]
    charges = [c["total_charge"] for c in claims]
    # Shorten drug names for display
    short_drugs = [d.split("(")[0].strip() if "(" in d else d for d in drugs]
    bars = ax1.barh(short_drugs, charges, color=colors, edgecolor="white", linewidth=0.5)
    ax1.set_xlabel("Total Charge ($)", color="white", fontsize=10)
    ax1.set_title("Charges by Drug", color="white", fontsize=13, fontweight="bold", pad=10)
    ax1.tick_params(colors="white")
    ax1.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    for bar, charge in zip(bars, charges):
        ax1.text(bar.get_width() + 80, bar.get_y() + bar.get_height() / 2,
                 f"${charge:,.0f}", va="center", color="white", fontsize=9)

    # ── Panel 2: Charges by Payer ──
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor("#16213e")
    payer_totals = {}
    for c in claims:
        payer = c.get("payer", "Unknown")
        payer_totals[payer] = payer_totals.get(payer, 0) + c["total_charge"]
    payers = list(payer_totals.keys())
    payer_charges = list(payer_totals.values())
    payer_colors = colors[:len(payers)]
    wedges, texts, autotexts = ax2.pie(
        payer_charges, labels=payers, colors=payer_colors, autopct="%1.0f%%",
        textprops={"color": "white", "fontsize": 9},
        wedgeprops={"edgecolor": "white", "linewidth": 0.5},
    )
    for t in autotexts:
        t.set_fontsize(10)
        t.set_fontweight("bold")
    ax2.set_title("Revenue by Payer", color="white", fontsize=13, fontweight="bold", pad=10)

    # ── Panel 3: Diagnosis Distribution ──
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.set_facecolor("#16213e")
    diag_counts = {}
    for c in claims:
        if c["diagnoses"]:
            primary = c["diagnoses"][0]["description"]
            diag_counts[primary] = diag_counts.get(primary, 0) + 1
    diag_names = list(diag_counts.keys())
    diag_vals = list(diag_counts.values())
    bars3 = ax3.bar(range(len(diag_names)), diag_vals, color=colors[:len(diag_names)],
                     edgecolor="white", linewidth=0.5)
    ax3.set_xticks(range(len(diag_names)))
    ax3.set_xticklabels(diag_names, rotation=30, ha="right", color="white", fontsize=8)
    ax3.set_ylabel("Patient Count", color="white", fontsize=10)
    ax3.set_title("Patients by Diagnosis", color="white", fontsize=13, fontweight="bold", pad=10)
    ax3.tick_params(colors="white")
    ax3.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    # ── Panel 4: Infusion Bay Schedule (from HL7 ADT) ──
    ax4 = fig.add_subplot(gs[1, 0:2])
    ax4.set_facecolor("#16213e")
    ax4.set_xlim(7.5, 13)
    ax4.set_ylim(0.5, 5.5)
    bay_map = {}
    for i, adm in enumerate(admissions):
        bay = adm.get("location", f"BAY{i+1}")
        if bay not in bay_map:
            bay_map[bay] = len(bay_map) + 1
        y = bay_map[bay]
        # Parse admission time
        time_str = adm.get("message_time", "")
        if len(time_str) >= 12:
            hour = int(time_str[8:10]) + int(time_str[10:12]) / 60
        else:
            hour = 8 + i
        # Estimate duration from number of procedures
        duration = max(1, len(adm.get("procedures", [])))
        bar = ax4.barh(y, duration, left=hour, height=0.6,
                       color=colors[i % len(colors)], edgecolor="white", linewidth=0.5,
                       alpha=0.85)
        label = f"{adm.get('patient', '?')}\n{adm.get('drug_name', '?')}"
        ax4.text(hour + duration / 2, y, label, ha="center", va="center",
                 color="white", fontsize=7.5, fontweight="bold")

    ax4.set_yticks(range(1, len(bay_map) + 1))
    ax4.set_yticklabels([f"Bay {b}" for b in bay_map.keys()], color="white", fontsize=10)
    ax4.set_xlabel("Time of Day", color="white", fontsize=10)
    ax4.set_title("Infusion Bay Schedule (from HL7 ADT)", color="white",
                  fontsize=13, fontweight="bold", pad=10)
    ax4.tick_params(colors="white")
    hours_range = range(8, 14)
    ax4.set_xticks(list(hours_range))
    ax4.set_xticklabels([f"{h}:00" for h in hours_range], color="white")
    ax4.grid(axis="x", color="#333366", linestyle="--", alpha=0.5)

    # ── Panel 5: Patient Summary Table ──
    ax5 = fig.add_subplot(gs[1, 2])
    ax5.set_facecolor("#16213e")
    ax5.axis("off")
    table_data = []
    for c in claims:
        table_data.append([
            c.get("patient", ""),
            c["diagnoses"][0]["description"][:15] if c["diagnoses"] else "",
            c.get("drug", "Unknown").split("(")[0].strip()[:12],
            f"${c['total_charge']:,.0f}",
        ])
    table = ax5.table(
        cellText=table_data,
        colLabels=["Patient", "Diagnosis", "Drug", "Charge"],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.8)
    for key, cell in table.get_celld().items():
        cell.set_edgecolor("#333366")
        if key[0] == 0:  # Header row
            cell.set_facecolor(accent)
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor("#1a1a2e")
            cell.set_text_props(color="white")
    ax5.set_title("Claims Summary", color="white", fontsize=13, fontweight="bold", pad=10)

    plt.savefig(output_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"Dashboard saved to: {output_path}")


# ── Main ─────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        input_dir = "/tmp/decrypted"
    else:
        input_dir = sys.argv[1]

    output_dir = sys.argv[2] if len(sys.argv) > 2 else "/tmp"
    output_path = os.path.join(output_dir, "infusion_dashboard.png")

    input_path = Path(input_dir)
    x12_files = sorted(input_path.glob("*.edi"))
    hl7_files = sorted(input_path.glob("*.hl7"))

    print(f"Found {len(x12_files)} X12 claims, {len(hl7_files)} HL7 admissions")

    claims = [parse_x12_837(f) for f in x12_files]
    admissions = [parse_hl7_adt(f) for f in hl7_files]

    # Print parsed summary
    print("\n── X12 837P Claims ─────────────────────────")
    for c in claims:
        print(f"  {c['patient']:20s} | {c.get('drug', 'N/A'):30s} | "
              f"${c['total_charge']:>8,.0f} | {c.get('payer', 'N/A')}")

    print("\n── HL7 ADT Admissions ──────────────────────")
    for a in admissions:
        print(f"  {a['patient']:20s} | Bay: {a.get('location', 'N/A'):6s} | "
              f"{a.get('attending_physician', 'N/A'):20s} | {a.get('drug_name', 'N/A')}")

    print(f"\nTotal billed: ${sum(c['total_charge'] for c in claims):,.0f}")
    print(f"Generating dashboard...")

    build_dashboard(claims, admissions, output_path)
    return output_path


if __name__ == "__main__":
    main()
