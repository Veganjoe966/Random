"""
90-Day Pharmacy Dispensing Record Generator
==========================================
Streamlit application for generating simulated pharmacy dispensing data.

PURPOSE: Compliance simulation, audit testing, and internal training ONLY.
         All generated data is clearly marked as SIMULATED and is not valid
         for any actual pharmaceutical, legal, or regulatory purpose.

Usage:
    streamlit run app.py
"""

import logging
import os
import sys
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Path setup — ensure src/ is importable
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))

from src.config import (
    DEFAULT_RECORD_COUNT,
    LOG_FILE,
    LOG_FORMAT,
    LOG_DATE_FORMAT,
    MAX_RECORD_COUNT,
    MIN_RECORD_COUNT,
    SIMULATION_DISCLAIMER,
)
from src.dea_parser import DEAParser, generate_prescriber_pool
from src.export_module import ExportModule
from src.ndc_service import NDCService
from src.record_generator import RecordGenerator
from src.validators import validate_dea, validate_npi

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Pharmacy Record Generator",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Disclaimer banner */
    .disclaimer-banner {
        background-color: #ff4b4b;
        color: white;
        font-weight: bold;
        text-align: center;
        padding: 10px 20px;
        border-radius: 6px;
        font-size: 15px;
        margin-bottom: 16px;
    }
    /* Section card */
    .section-card {
        background-color: #f0f4ff;
        border-left: 5px solid #1F3864;
        border-radius: 4px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }
    /* Valid field */
    .field-valid {color: #2e7d32; font-weight: bold;}
    /* Invalid field */
    .field-invalid {color: #c62828; font-weight: bold;}
    /* Metric cards */
    div[data-testid="metric-container"] {
        background-color: #EFF3FB;
        border: 1px solid #BDD7EE;
        border-radius: 8px;
        padding: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Disclaimer Banner
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="disclaimer-banner">'
    "⚠️  SIMULATED DATA — FOR COMPLIANCE TRAINING AND AUDIT TESTING ONLY  ⚠️<br>"
    "All generated records are entirely synthetic and have no legal, regulatory, "
    "or pharmaceutical validity."
    "</div>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

st.title("💊 90-Day Pharmacy Dispensing Record Generator")
st.caption(
    "Production-grade simulation engine for compliance training, audit testing, "
    "and internal staff development."
)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

if "generated_df" not in st.session_state:
    st.session_state["generated_df"] = None
if "export_module" not in st.session_state:
    st.session_state["export_module"] = None
if "generation_complete" not in st.session_state:
    st.session_state["generation_complete"] = False
if "prescribers" not in st.session_state:
    st.session_state["prescribers"] = None
if "validation_issues" not in st.session_state:
    st.session_state["validation_issues"] = []
if "parse_errors" not in st.session_state:
    st.session_state["parse_errors"] = []


# ===========================================================================
# SIDEBAR — Pharmacy Configuration
# ===========================================================================

with st.sidebar:
    st.header("🏥 Pharmacy Configuration")
    st.caption("Enter pharmacy details for record generation.")

    st.divider()

    # --- Pharmacy Name ---
    pharmacy_name = st.text_input(
        "Pharmacy Name *",
        value="City Medical Pharmacy",
        help="Name of the dispensing pharmacy.",
    )

    # --- NPI ---
    npi_input = st.text_input(
        "Pharmacy NPI *",
        value="1234567893",
        max_chars=10,
        help="10-digit National Provider Identifier (NPI).",
    )

    npi_ok, npi_msg = validate_npi(npi_input)
    if npi_input:
        color = "field-valid" if npi_ok else "field-invalid"
        icon  = "✅" if npi_ok else "❌"
        st.markdown(
            f'<span class="{color}">{icon} {npi_msg}</span>',
            unsafe_allow_html=True,
        )

    # --- DEA Number ---
    dea_input = st.text_input(
        "Pharmacy DEA Number *",
        value="AB1234563",
        max_chars=9,
        help="DEA registration number (2 letters + 7 digits).",
    )

    dea_ok, dea_msg = validate_dea(dea_input)
    if dea_input:
        color = "field-valid" if dea_ok else "field-invalid"
        icon  = "✅" if dea_ok else "❌"
        st.markdown(
            f'<span class="{color}">{icon} {dea_msg}</span>',
            unsafe_allow_html=True,
        )

    # --- Address ---
    address = st.text_input(
        "Street Address",
        value="123 Main Street, Suite 100",
    )

    col_city, col_state = st.columns([2, 1])
    with col_city:
        city = st.text_input("City", value="Springfield")
    with col_state:
        state = st.text_input("State", value="IL", max_chars=2)

    col_zip, _ = st.columns([1, 1])
    with col_zip:
        zip_code = st.text_input("ZIP Code", value="62701", max_chars=5)

    st.divider()

    # --- Reporting Period ---
    st.subheader("📅 Reporting Period")

    today = date.today()
    default_end   = today
    default_start = today - timedelta(days=89)

    report_end   = st.date_input("Period End Date", value=default_end)
    report_start = report_end - timedelta(days=89)

    st.info(
        f"**90-Day Window:**  \n"
        f"{report_start.strftime('%B %d, %Y')} → {report_end.strftime('%B %d, %Y')}"
    )

    st.divider()

    # --- Record Count ---
    st.subheader("📊 Generation Volume")

    record_count = st.slider(
        "Target Record Count",
        min_value=MIN_RECORD_COUNT,
        max_value=MAX_RECORD_COUNT,
        value=DEFAULT_RECORD_COUNT,
        step=100,
        help="Number of dispensing records to simulate.",
    )

    st.caption(
        f"Estimated mix: ~{int(record_count * 0.28):,} controlled / "
        f"~{int(record_count * 0.72):,} non-controlled"
    )

    st.divider()

    # --- State Filter ---
    st.subheader("🗺️ State Filter")
    st.caption("Restrict patients and prescribers to a single state.")

    _US_STATES = {
        "AL": "Alabama",        "AK": "Alaska",         "AZ": "Arizona",
        "AR": "Arkansas",       "CA": "California",     "CO": "Colorado",
        "CT": "Connecticut",    "DE": "Delaware",       "FL": "Florida",
        "GA": "Georgia",        "HI": "Hawaii",         "ID": "Idaho",
        "IL": "Illinois",       "IN": "Indiana",        "IA": "Iowa",
        "KS": "Kansas",         "KY": "Kentucky",       "LA": "Louisiana",
        "ME": "Maine",          "MD": "Maryland",       "MA": "Massachusetts",
        "MI": "Michigan",       "MN": "Minnesota",      "MS": "Mississippi",
        "MO": "Missouri",       "MT": "Montana",        "NE": "Nebraska",
        "NV": "Nevada",         "NH": "New Hampshire",  "NJ": "New Jersey",
        "NM": "New Mexico",     "NY": "New York",       "NC": "North Carolina",
        "ND": "North Dakota",   "OH": "Ohio",           "OK": "Oklahoma",
        "OR": "Oregon",         "PA": "Pennsylvania",   "RI": "Rhode Island",
        "SC": "South Carolina", "SD": "South Dakota",   "TN": "Tennessee",
        "TX": "Texas",          "UT": "Utah",           "VT": "Vermont",
        "VA": "Virginia",       "WA": "Washington",     "WV": "West Virginia",
        "WI": "Wisconsin",      "WY": "Wyoming",
    }

    state_options = ["All States (random)"] + [
        f"{abbr} — {name}" for abbr, name in sorted(_US_STATES.items(), key=lambda x: x[1])
    ]

    state_selection = st.selectbox(
        "Target State",
        state_options,
        index=0,
        help=(
            "When a state is selected: patient addresses are restricted to that "
            "state and prescribers are filtered (uploaded) or generated (auto) "
            "for that state."
        ),
    )

    target_state: Optional[str] = (
        None if state_selection == "All States (random)"
        else state_selection.split(" — ")[0]
    )


# ===========================================================================
# MAIN PANEL
# ===========================================================================

tab_upload, tab_generate, tab_results = st.tabs([
    "📁 Step 1 — Upload Prescriber List",
    "⚙️  Step 2 — Generate Records",
    "📊 Step 3 — Results & Export",
])


# ---------------------------------------------------------------------------
# TAB 1 — DEA File Upload
# ---------------------------------------------------------------------------

with tab_upload:
    st.header("Prescriber / DEA File Upload")
    st.markdown(
        """
        Upload a prescriber list in **CSV, Excel, or JSON** format.
        Supported columns (flexible naming — header auto-detected):

        | Field | Example Headers |
        |---|---|
        | Prescriber Name | `Prescriber Name`, `Provider Name`, `Name` |
        | DEA Number | `DEA Number`, `DEA#`, `DEA` |
        | NPI | `NPI`, `NPI Number`, `Provider ID` |
        | Specialty | `Specialty`, `Provider Type` |
        | ZIP Code | `ZIP`, `Zip Code`, `Postal Code` |
        | Address | `Address`, `Street Address` |

        If no file is uploaded, a **realistic simulated prescriber pool** will be generated automatically.

        **JSON format** — supply an array of objects (or an object with one array-valued key):
        ```json
        [
          {"prescriber_name": "Dr. Jane Smith", "dea_number": "BS1234563",
           "npi": "1234567893", "specialty": "Pain Management",
           "state": "TX", "zip": "77001"}
        ]
        ```
        """
    )

    uploaded_file = st.file_uploader(
        "Upload DEA / Prescriber List",
        type=["csv", "xlsx", "xls", "json"],
        help="Accepted formats: CSV, Excel (.xlsx, .xls), JSON (.json)",
    )

    if uploaded_file is not None:
        st.info(f"File received: **{uploaded_file.name}** ({uploaded_file.size:,} bytes)")

        with st.spinner("Parsing prescriber file..."):
            parser = DEAParser()
            file_bytes = uploaded_file.read()
            success = parser.parse(file_bytes, uploaded_file.name)

        if not success:
            st.error("Failed to parse file. Errors:")
            for err in parser.parse_errors:
                st.error(f"• {err}")
        else:
            st.session_state["prescribers"]       = parser.prescribers
            st.session_state["validation_issues"] = parser.validation_report
            st.session_state["parse_errors"]       = parser.parse_errors

            st.success(
                f"✅  Parsed **{len(parser.prescribers):,}** prescribers from "
                f"**{uploaded_file.name}**."
            )

            # Validation report
            if parser.validation_report:
                st.warning(
                    f"⚠️  **{len(parser.validation_report)}** DEA validation issue(s) detected. "
                    "These will appear in the Validation Report sheet of your Excel export."
                )
                with st.expander("View Validation Issues"):
                    st.dataframe(
                        parser.get_validation_report_df(),
                        use_container_width=True,
                    )

            # Preview parsed prescribers
            with st.expander(f"Preview Parsed Prescribers ({len(parser.prescribers)} records)"):
                prev_df = pd.DataFrame(parser.prescribers).drop(
                    columns=["source"], errors="ignore"
                )
                st.dataframe(prev_df.head(50), use_container_width=True)

    else:
        st.info(
            "ℹ️  No file uploaded. A simulated prescriber pool will be created automatically "
            "when you generate records."
        )

        if st.button("Preview Auto-Generated Prescriber Pool"):
            with st.spinner("Generating sample prescriber pool..."):
                sample = generate_prescriber_pool(count=20)
            st.dataframe(
                pd.DataFrame(sample).drop(columns=["source"], errors="ignore"),
                use_container_width=True,
            )


# ---------------------------------------------------------------------------
# TAB 2 — Generate
# ---------------------------------------------------------------------------

with tab_generate:
    st.header("Generate Dispensing Records")

    # Validate required fields before allowing generation
    config_valid = bool(pharmacy_name.strip())
    if not config_valid:
        st.warning("Please enter a Pharmacy Name in the sidebar before generating.")

    # Summary of config
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Configuration Summary**")
        st.markdown(
            f"""
            | Field | Value |
            |---|---|
            | Pharmacy | {pharmacy_name} |
            | NPI | {npi_input} |
            | DEA | {dea_input} |
            | City / State | {city}, {state} |
            | Period | {report_start.strftime('%m/%d/%Y')} – {report_end.strftime('%m/%d/%Y')} |
            | Target Records | {record_count:,} |
            | State Filter | {target_state if target_state else "All States"} |
            """
        )

    with col2:
        st.markdown("**Estimated Record Mix**")
        n_ctrl   = int(record_count * 0.28)
        n_nctrl  = record_count - n_ctrl
        n_cii    = int(n_ctrl * 0.38)
        n_ciii   = int(n_ctrl * 0.12)
        n_civ    = int(n_ctrl * 0.42)
        n_cv     = n_ctrl - n_cii - n_ciii - n_civ

        st.markdown(
            f"""
            | Schedule | Count |
            |---|---|
            | Schedule II (CII) | ~{n_cii:,} |
            | Schedule III (CIII) | ~{n_ciii:,} |
            | Schedule IV (CIV) | ~{n_civ:,} |
            | Schedule V (CV) | ~{n_cv:,} |
            | **Total Controlled** | **~{n_ctrl:,}** |
            | Non-Controlled | ~{n_nctrl:,} |
            | **Grand Total** | **{record_count:,}** |
            """
        )

    st.divider()

    # Optional: prescriber pool status
    if st.session_state["prescribers"]:
        n_prescribers = len(st.session_state["prescribers"])
        st.success(f"Prescriber pool: **{n_prescribers}** prescribers loaded from uploaded file.")
    else:
        st.info("Prescriber pool: Auto-generated (60 simulated prescribers).")

    st.divider()

    # Generation button
    generate_btn = st.button(
        "🚀  Generate Records",
        type="primary",
        disabled=not config_valid,
        use_container_width=True,
    )

    if generate_btn:
        pharmacy_config = {
            "pharmacy_name": pharmacy_name.strip(),
            "npi":           npi_input.strip(),
            "dea_number":    dea_input.strip().upper(),
            "address":       address.strip(),
            "city":          city.strip(),
            "state":         state.strip().upper(),
            "zip":           zip_code.strip(),
        }

        # Prepare prescriber pool
        raw_prescribers = st.session_state.get("prescribers")
        if raw_prescribers:
            if target_state:
                # Filter uploaded prescribers to the selected state
                prescribers = [
                    p for p in raw_prescribers
                    if p.get("state", "").strip().upper() == target_state
                ]
                if not prescribers:
                    status_text.warning(
                        f"⚠️  No uploaded prescribers found for state '{target_state}'. "
                        "Using full uploaded pool."
                    )
                    prescribers = raw_prescribers
            else:
                prescribers = raw_prescribers
        else:
            prescribers = generate_prescriber_pool(count=60, target_state=target_state)

        # Initialize services
        ndc_service = NDCService()

        # Progress UI
        progress_bar  = st.progress(0, text="Initializing generation engine...")
        status_text   = st.empty()

        def progress_callback(pct: float) -> None:
            progress_bar.progress(
                min(pct, 1.0),
                text=f"Generating records... {int(pct * 100)}%",
            )

        try:
            status_text.info("🔍  Pre-fetching NDC data from FDA API...")
            generator = RecordGenerator(
                pharmacy_config=pharmacy_config,
                ndc_service=ndc_service,
                prescribers=prescribers,
                target_state=target_state,
            )

            status_text.info("⚙️  Generating dispensing records...")
            df = generator.generate(
                num_records=record_count,
                start_date=report_start,
                end_date=report_end,
                progress_callback=progress_callback,
            )

            progress_bar.progress(1.0, text="Generation complete!")

            date_range_str = (
                f"{report_start.strftime('%B %d, %Y')} — {report_end.strftime('%B %d, %Y')}"
            )

            export_mod = ExportModule(
                df=df,
                pharmacy_config=pharmacy_config,
                date_range_str=date_range_str,
                validation_issues=st.session_state.get("validation_issues", []),
            )

            st.session_state["generated_df"]      = df
            st.session_state["export_module"]     = export_mod
            st.session_state["generation_complete"] = True

            status_text.success(
                f"✅  Successfully generated **{len(df):,}** dispensing records. "
                "Switch to the **Results & Export** tab to download."
            )
            logger.info("Generated %d records for pharmacy '%s'.", len(df), pharmacy_name)

        except Exception as exc:
            progress_bar.empty()
            status_text.error(f"Generation failed: {exc}")
            logger.exception("Record generation failed.")


# ---------------------------------------------------------------------------
# TAB 3 — Results & Export
# ---------------------------------------------------------------------------

with tab_results:
    st.header("Results & Export")

    df: Optional[pd.DataFrame] = st.session_state.get("generated_df")
    export_mod: Optional[ExportModule] = st.session_state.get("export_module")

    if df is None:
        st.info("No records generated yet. Complete Steps 1 & 2 first.")
    else:
        # KPI Metrics Row
        total = len(df)
        n_cii_actual  = len(df[df["controlled_schedule"] == "Schedule II"])
        n_ciii_actual = len(df[df["controlled_schedule"] == "Schedule III"])
        n_civ_actual  = len(df[df["controlled_schedule"] == "Schedule IV"])
        n_cv_actual   = len(df[df["controlled_schedule"] == "Schedule V"])
        n_ctrl_actual = n_cii_actual + n_ciii_actual + n_civ_actual + n_cv_actual
        n_nctrl_actual = len(df[df["controlled_schedule"] == "Non-Controlled"])
        n_cash   = len(df[df["payment_type"] == "Cash"])
        n_ins    = len(df[df["payment_type"] == "Insurance"])

        st.markdown("### 📈 Summary Metrics")
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Total Records",  f"{total:,}")
        m2.metric("Schedule II",    f"{n_cii_actual:,}")
        m3.metric("CIII–V",         f"{n_ciii_actual + n_civ_actual + n_cv_actual:,}")
        m4.metric("Non-Controlled", f"{n_nctrl_actual:,}")
        m5.metric("Cash Fills",     f"{n_cash:,}")
        m6.metric("Insurance",      f"{n_ins:,}")

        st.divider()

        # Top Drugs Chart
        st.markdown("### 💊 Top 15 Dispensed Medications")
        top_drugs = (
            df["drug_name"]
            .value_counts()
            .head(15)
            .reset_index()
        )
        top_drugs.columns = ["Drug", "Count"]
        st.bar_chart(top_drugs.set_index("Drug"))

        st.divider()

        # Data Preview
        st.markdown("### 🔍 Record Preview")

        filter_col, filter_val_col = st.columns([1, 2])
        with filter_col:
            filter_field = st.selectbox(
                "Filter by",
                ["(No filter)", "controlled_schedule", "payment_type", "prescriber_specialty"],
            )
        with filter_val_col:
            if filter_field != "(No filter)" and filter_field in df.columns:
                filter_options = ["(All)"] + sorted(df[filter_field].unique().tolist())
                filter_val = st.selectbox("Value", filter_options)
            else:
                filter_val = "(All)"

        display_df = df.copy()
        if filter_field != "(No filter)" and filter_val != "(All)":
            display_df = display_df[display_df[filter_field] == filter_val]

        st.dataframe(
            display_df.head(500),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"Showing first 500 of {len(display_df):,} records"
            f"{f' (filtered from {total:,})' if len(display_df) < total else ''}."
        )

        st.divider()

        # Export Buttons
        st.markdown("### 📥 Export Records")

        col_excel, col_csv = st.columns(2)

        with col_excel:
            st.markdown("**Excel (.xlsx)** — Includes Summary Sheet, auto-widths, frozen header")
            try:
                excel_bytes = export_mod.to_excel_bytes()
                filename_excel = (
                    f"SimulatedDispensing_{pharmacy_name.replace(' ', '_')}_"
                    f"{report_start.strftime('%Y%m%d')}_{report_end.strftime('%Y%m%d')}.xlsx"
                )
                st.download_button(
                    label="⬇️  Download Excel (.xlsx)",
                    data=excel_bytes,
                    file_name=filename_excel,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    type="primary",
                )
            except Exception as exc:
                st.error(f"Excel export failed: {exc}")
                logger.exception("Excel export error.")

        with col_csv:
            st.markdown("**CSV** — Flat file for import into other systems")
            try:
                csv_bytes = export_mod.to_csv_bytes()
                filename_csv = (
                    f"SimulatedDispensing_{pharmacy_name.replace(' ', '_')}_"
                    f"{report_start.strftime('%Y%m%d')}_{report_end.strftime('%Y%m%d')}.csv"
                )
                st.download_button(
                    label="⬇️  Download CSV",
                    data=csv_bytes,
                    file_name=filename_csv,
                    mime="text/csv",
                    use_container_width=True,
                )
            except Exception as exc:
                st.error(f"CSV export failed: {exc}")

        st.divider()

        # Validation Issues
        if st.session_state["validation_issues"]:
            st.markdown("### ⚠️ DEA Validation Issues from Upload")
            val_df = pd.DataFrame(st.session_state["validation_issues"])
            st.dataframe(val_df, use_container_width=True, hide_index=True)

        # Disclaimer footer
        st.divider()
        st.markdown(
            f"""
            <div style="
                background: #fff3cd;
                border: 2px solid #ffc107;
                border-radius: 6px;
                padding: 12px 16px;
                font-size: 13px;
            ">
            <strong>⚠️ Data Use Disclaimer:</strong><br>
            {SIMULATION_DISCLAIMER.replace(chr(10), '<br>')}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.markdown(
    """
    <div style="text-align:center; color:#888; font-size:12px;">
    Pharmacy Record Generator | Compliance Simulation Engine<br>
    <strong>All data is SIMULATED. No real patient, prescriber, or pharmacy data is used.</strong>
    </div>
    """,
    unsafe_allow_html=True,
)
