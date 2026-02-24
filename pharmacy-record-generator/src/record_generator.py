"""
Core Pharmacy Dispensing Record Generator.

Generates clinically realistic simulated dispensing records for compliance
training, audit simulation, and internal testing purposes only.

Architecture:
  - Patient pool: generated once, reused across fills
  - Prescriber pool: from uploaded DEA file or auto-generated
  - Drug selection: weighted random, respecting controlled/non-controlled ratios
  - Refill logic: tracks per-patient, per-drug fill history
  - Date distribution: weighted toward weekdays with realistic daily volume
  - NDC lookup: delegated to NDCService with caching
"""

import logging
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from .config import (
    CASH_RATIO_CONTROLLED,
    CASH_RATIO_NON_CONTROLLED,
    CII_RATIO,
    CIII_RATIO,
    CIV_RATIO,
    CONTROLLED_RATIO,
    CV_RATIO,
    INSURANCE_PLANS,
    NON_CONTROLLED_RATIO,
    RX_BASE_MAX,
    RX_BASE_MIN,
    SCHEDULE_LABELS,
    SIMULATION_DISCLAIMER,
)
from .drug_database import CONTROLLED_DRUGS, NON_CONTROLLED_DRUGS, DrugDef
from .ndc_service import NDCService
from .validators import generate_valid_dea, generate_valid_npi

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patient Name / Address Data
# ---------------------------------------------------------------------------

_MALE_FIRST = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard",
    "Joseph", "Thomas", "Charles", "Christopher", "Daniel", "Matthew",
    "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
    "Kevin", "Brian", "Edward", "Ronald", "Timothy", "Jason", "Jeffrey",
    "Ryan", "Jacob", "Gary", "Eric", "Jonathan", "Stephen", "Larry",
    "Scott", "Frank", "Brandon", "Raymond", "Gregory", "Benjamin",
]

_FEMALE_FIRST = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth",
    "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Margaret",
    "Betty", "Dorothy", "Sandra", "Ashley", "Emily", "Kimberly", "Carol",
    "Michelle", "Amanda", "Melissa", "Deborah", "Stephanie", "Rebecca",
    "Sharon", "Laura", "Cynthia", "Kathleen", "Amy", "Angela", "Shirley",
    "Anna", "Brenda", "Pamela", "Emma", "Nicole", "Helen", "Samantha",
]

_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson",
    "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee",
    "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez",
    "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright",
    "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams",
    "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter",
    "Roberts", "Gomez",
]

_STREET_TYPES = [
    "St", "Ave", "Blvd", "Dr", "Ln", "Rd", "Ct", "Way", "Pl", "Circle",
]

_STREET_NAMES = [
    "Main", "Oak", "Maple", "Cedar", "Pine", "Elm", "Washington", "Park",
    "Lake", "Hill", "Sunset", "River", "Spring", "Meadow", "Forest",
    "Valley", "Highland", "Riverside", "Greenwood", "Willowbrook",
    "Churchhill", "Heritage", "Liberty", "Lincoln", "Jefferson", "Madison",
    "Monroe", "Harrison", "Dewey", "Franklin", "Commerce", "Center",
]

_CITIES_STATES_ZIPS = [
    ("Springfield",   "IL", "62701"),
    ("Franklin",      "TN", "37067"),
    ("Greenville",    "SC", "29601"),
    ("Bristol",       "VA", "24201"),
    ("Fairview",      "TX", "75069"),
    ("Georgetown",    "KY", "40324"),
    ("Chester",       "PA", "19013"),
    ("Madison",       "WI", "53703"),
    ("Salem",         "OR", "97301"),
    ("Burlington",    "VT", "05401"),
    ("Lexington",     "KY", "40502"),
    ("Columbia",      "MO", "65201"),
    ("Oakland",       "CA", "94601"),
    ("Raleigh",       "NC", "27601"),
    ("Tulsa",         "OK", "74101"),
    ("Aurora",        "CO", "80010"),
    ("Richmond",      "VA", "23220"),
    ("Baton Rouge",   "LA", "70801"),
    ("Tucson",        "AZ", "85701"),
    ("Des Moines",    "IA", "50301"),
]

# Day-of-week fill weights: Mon=high, Sat=low, Sun=very low
_DOW_WEIGHTS = [1.30, 1.20, 1.10, 1.10, 1.15, 0.60, 0.25]   # Mon–Sun


# ---------------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------------

def _weighted_choice(options: list, weights: list):
    """Random choice with weights (avoids numpy dependency)."""
    return random.choices(options, weights=weights, k=1)[0]


def _date_range(start: date, end: date) -> List[date]:
    """Return all dates from start to end inclusive."""
    delta = (end - start).days + 1
    return [start + timedelta(days=i) for i in range(delta)]


def _build_date_pool(start: date, end: date) -> List[date]:
    """
    Build a weighted pool of dates across the 90-day range.
    Weekdays appear more often; weekends are rare.
    """
    pool = []
    for d in _date_range(start, end):
        weight = _DOW_WEIGHTS[d.weekday()]
        # Slight end-of-month refill bump
        if d.day >= 28:
            weight *= 1.10
        repeats = max(1, int(weight * 10))
        pool.extend([d] * repeats)
    return pool


def _random_dob(age_min: int, age_max: int, ref_date: date) -> date:
    """Generate a random DOB such that age falls in [age_min, age_max] on ref_date."""
    age_days = random.randint(age_min * 365, age_max * 365)
    return ref_date - timedelta(days=age_days)


def _format_date(d: date) -> str:
    return d.strftime("%m/%d/%Y")


# ---------------------------------------------------------------------------
# Patient Generation
# ---------------------------------------------------------------------------

def _generate_patient(patient_id: int, drug_def: DrugDef, ref_date: date) -> Dict[str, Any]:
    """Create a single patient record with demographics."""
    gender = random.choice(["M", "F"])
    first  = random.choice(_MALE_FIRST if gender == "M" else _FEMALE_FIRST)
    last   = random.choice(_LAST_NAMES)

    age_min, age_max = drug_def.get("patient_age_range", (18, 75))
    dob = _random_dob(age_min, age_max, ref_date)

    city, state, zip_code = random.choice(_CITIES_STATES_ZIPS)
    street_num  = random.randint(100, 9999)
    street_name = random.choice(_STREET_NAMES)
    street_type = random.choice(_STREET_TYPES)
    address     = f"{street_num} {street_name} {street_type}"

    return {
        "patient_id":    patient_id,
        "patient_name":  f"{first} {last}",
        "patient_dob":   _format_date(dob),
        "patient_address": address,
        "patient_city":  city,
        "patient_state": state,
        "patient_zip":   zip_code,
        "gender":        gender,
    }


# ---------------------------------------------------------------------------
# Record Generator
# ---------------------------------------------------------------------------

class RecordGenerator:
    """
    Primary engine for generating simulated pharmacy dispensing records.

    Parameters
    ----------
    pharmacy_config : dict
        Keys: pharmacy_name, npi, dea_number, address, city, state, zip
    ndc_service     : NDCService
        Pre-initialized NDC lookup service
    prescribers     : list
        Pool of prescriber dicts from DEAParser or simulate
    seed            : int, optional
        Random seed for reproducibility
    """

    def __init__(
        self,
        pharmacy_config: Dict[str, Any],
        ndc_service: NDCService,
        prescribers: List[Dict[str, Any]],
        seed: Optional[int] = None,
    ) -> None:
        self.pharmacy     = pharmacy_config
        self.ndc_service  = ndc_service
        self.prescribers  = prescribers
        self.seed         = seed

        if seed is not None:
            random.seed(seed)

        self._rx_counter  = random.randint(RX_BASE_MIN, RX_BASE_MAX)
        self._rx_gap_pool = [0, 0, 0, 1, 1, 2, 3]   # gaps between sequential RX numbers

        # Preload specialties for prescriber affinity lookup
        self._build_specialty_index()

    # ------------------------------------------------------------------
    # Public Entry Point
    # ------------------------------------------------------------------

    def generate(
        self,
        num_records: int,
        start_date: date,
        end_date: date,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> pd.DataFrame:
        """
        Generate `num_records` simulated dispensing records.

        Parameters
        ----------
        num_records       : int
        start_date        : date — first day of 90-day window
        end_date          : date — last day of 90-day window
        progress_callback : callable(float) — receives 0.0–1.0 progress

        Returns
        -------
        pd.DataFrame  — one row per dispensing record
        """
        logger.info(
            "Starting generation: %d records, %s → %s",
            num_records, start_date, end_date,
        )

        date_pool = _build_date_pool(start_date, end_date)

        # Determine counts per schedule
        n_controlled     = int(num_records * CONTROLLED_RATIO)
        n_non_controlled = num_records - n_controlled

        n_cii   = int(n_controlled * CII_RATIO)
        n_ciii  = int(n_controlled * CIII_RATIO)
        n_civ   = int(n_controlled * CIV_RATIO)
        n_cv    = n_controlled - n_cii - n_ciii - n_civ

        schedule_plan = (
            [("CII",  d) for d in CONTROLLED_DRUGS["CII"]]  * max(1, n_cii  // len(CONTROLLED_DRUGS["CII"]))  +
            [("CIII", d) for d in CONTROLLED_DRUGS["CIII"]] * max(1, n_ciii // len(CONTROLLED_DRUGS["CIII"])) +
            [("CIV",  d) for d in CONTROLLED_DRUGS["CIV"]]  * max(1, n_civ  // len(CONTROLLED_DRUGS["CIV"]))  +
            [("CV",   d) for d in CONTROLLED_DRUGS["CV"]]   * max(1, n_cv   // len(CONTROLLED_DRUGS["CV"]))
        )

        non_ctrl_plan = (
            NON_CONTROLLED_DRUGS * max(1, n_non_controlled // len(NON_CONTROLLED_DRUGS))
        )

        # Pre-fetch NDC data for all drugs in the plan
        all_search_terms = list({
            d["search_term"]
            for (_, d) in schedule_plan
        } | {d["search_term"] for d in non_ctrl_plan})

        logger.info("Pre-fetching %d NDC entries...", len(all_search_terms))
        self.ndc_service.preload(all_search_terms)

        # Generate patient pool (35–50% of target count = unique patients)
        num_patients = max(20, int(num_records * random.uniform(0.35, 0.50)))
        patients: Dict[int, Dict[str, Any]] = {}

        # Fill history: patient_id → {drug_name: [fill_dates]}
        fill_history: Dict[int, Dict[str, List[date]]] = defaultdict(lambda: defaultdict(list))

        records: List[Dict[str, Any]] = []

        # Generate controlled records
        ctrl_records = self._generate_controlled_records(
            n_cii, n_ciii, n_civ, n_cv,
            date_pool, patients, fill_history,
        )
        records.extend(ctrl_records)

        # Generate non-controlled records
        nc_records = self._generate_non_controlled_records(
            n_non_controlled,
            date_pool, patients, fill_history,
        )
        records.extend(nc_records)

        # Shuffle and assign dates naturally
        random.shuffle(records)

        # Sort by date for realistic ordering
        records.sort(key=lambda r: r["_sort_date"])

        # Assign sequential RX numbers
        logger.info("Assigning RX numbers and finalizing %d records...", len(records))
        for i, rec in enumerate(records):
            gap = random.choice(self._rx_gap_pool)
            self._rx_counter += 1 + gap
            rec["rx_number"] = str(self._rx_counter)
            del rec["_sort_date"]       # internal field

            if progress_callback:
                progress_callback((i + 1) / len(records))

        df = pd.DataFrame(records)

        # Ensure column order
        df = df[self._column_order()]

        logger.info("Generation complete: %d records produced.", len(df))
        return df

    # ------------------------------------------------------------------
    # Controlled Substance Record Generation
    # ------------------------------------------------------------------

    def _generate_controlled_records(
        self,
        n_cii: int, n_ciii: int, n_civ: int, n_cv: int,
        date_pool: List[date],
        patients: Dict[int, Dict[str, Any]],
        fill_history: Dict,
    ) -> List[Dict[str, Any]]:
        records = []

        schedule_counts = [
            ("CII",  n_cii),
            ("CIII", n_ciii),
            ("CIV",  n_civ),
            ("CV",   n_cv),
        ]

        for schedule, count in schedule_counts:
            if count <= 0:
                continue
            drugs = CONTROLLED_DRUGS[schedule]
            generated = 0

            while generated < count:
                drug = random.choice(drugs)
                fill_date = random.choice(date_pool)

                patient, pat_id = self._get_or_create_patient(patients, drug, fill_date)

                # Determine refill number
                refill_num = self._compute_refill_number(
                    pat_id, drug, fill_date, fill_history
                )

                # CII: new Rx each time (refill_num always 0 for new Rx)
                if schedule == "CII" and refill_num > 0:
                    # Each CII fill requires a new written Rx - simulate with refill=0
                    # but still track the history to prevent early fills
                    pass

                # Check for unrealistically early refill (< 25 days from last fill)
                last_fills = fill_history[pat_id][drug["name"]]
                if last_fills:
                    last_fill = max(last_fills)
                    days_since = (fill_date - last_fill).days
                    if days_since < 25:
                        continue        # skip — too early, would flag as early fill

                fill_history[pat_id][drug["name"]].append(fill_date)

                prescriber = self._select_prescriber(drug, schedule)
                ndc_result = self.ndc_service.lookup(drug["search_term"])
                strength   = _weighted_choice(drug["strengths"], drug["strength_weights"])
                quantity   = _weighted_choice(drug["typical_quantities"], drug["qty_weights"])
                days_supply = random.choice(drug["days_supply_options"])
                payment, insurance = self._pick_payment(is_controlled=True)

                rec = {
                    "rx_number":          "",            # assigned later
                    "fill_date":          _format_date(fill_date),
                    "patient_name":       patient["patient_name"],
                    "patient_dob":        patient["patient_dob"],
                    "patient_address":    patient["patient_address"],
                    "patient_city":       patient["patient_city"],
                    "patient_state":      patient["patient_state"],
                    "patient_zip":        patient["patient_zip"],
                    "drug_name":          drug["name"],
                    "brand_name":         random.choice(drug["brand_names"]),
                    "strength":           strength,
                    "dosage_form":        drug["dosage_form"],
                    "quantity":           quantity,
                    "days_supply":        days_supply,
                    "refill_number":      0 if schedule == "CII" else min(refill_num, drug["max_refills"]),
                    "prescriber_name":    prescriber["prescriber_name"],
                    "prescriber_dea":     prescriber.get("dea_number", ""),
                    "prescriber_npi":     prescriber.get("npi", ""),
                    "prescriber_specialty": prescriber.get("specialty", ""),
                    "prescriber_zip":     prescriber.get("zip", ""),
                    "ndc":                ndc_result.ndc,
                    "ndc_labeler":        ndc_result.labeler,
                    "payment_type":       payment,
                    "insurance_plan":     insurance,
                    "controlled_schedule": SCHEDULE_LABELS[schedule],
                    "diagnosis":          random.choice(drug["diagnoses"]),
                    "data_status":        "SIMULATED — TRAINING ONLY",
                    "_sort_date":         fill_date,
                }
                records.append(rec)
                generated += 1

        return records

    # ------------------------------------------------------------------
    # Non-Controlled Record Generation
    # ------------------------------------------------------------------

    def _generate_non_controlled_records(
        self,
        count: int,
        date_pool: List[date],
        patients: Dict[int, Dict[str, Any]],
        fill_history: Dict,
    ) -> List[Dict[str, Any]]:
        records = []
        generated = 0

        while generated < count:
            drug = random.choice(NON_CONTROLLED_DRUGS)
            fill_date = random.choice(date_pool)

            patient, pat_id = self._get_or_create_patient(patients, drug, fill_date)

            # Refill logic
            refill_num = self._compute_refill_number(pat_id, drug, fill_date, fill_history)

            # Non-controlled acute meds (max_refills=0): only new fills
            if drug["max_refills"] == 0 and refill_num > 0:
                # check minimum spacing for acute meds (7-14 days)
                last_fills = fill_history[pat_id][drug["name"]]
                if last_fills:
                    days_since = (fill_date - max(last_fills)).days
                    if days_since < 7:
                        continue

            fill_history[pat_id][drug["name"]].append(fill_date)

            prescriber = self._select_prescriber(drug, "Non-Control")
            ndc_result = self.ndc_service.lookup(drug["search_term"])
            strength   = _weighted_choice(drug["strengths"], drug["strength_weights"])
            quantity   = _weighted_choice(drug["typical_quantities"], drug["qty_weights"])
            days_supply = random.choice(drug["days_supply_options"])
            payment, insurance = self._pick_payment(is_controlled=False)

            rec = {
                "rx_number":          "",
                "fill_date":          _format_date(fill_date),
                "patient_name":       patient["patient_name"],
                "patient_dob":        patient["patient_dob"],
                "patient_address":    patient["patient_address"],
                "patient_city":       patient["patient_city"],
                "patient_state":      patient["patient_state"],
                "patient_zip":        patient["patient_zip"],
                "drug_name":          drug["name"],
                "brand_name":         random.choice(drug["brand_names"]),
                "strength":           strength,
                "dosage_form":        drug["dosage_form"],
                "quantity":           quantity,
                "days_supply":        days_supply,
                "refill_number":      min(refill_num, drug["max_refills"]),
                "prescriber_name":    prescriber["prescriber_name"],
                "prescriber_dea":     "",                    # non-controlled: no DEA required
                "prescriber_npi":     prescriber.get("npi", ""),
                "prescriber_specialty": prescriber.get("specialty", ""),
                "prescriber_zip":     prescriber.get("zip", ""),
                "ndc":                ndc_result.ndc,
                "ndc_labeler":        ndc_result.labeler,
                "payment_type":       payment,
                "insurance_plan":     insurance,
                "controlled_schedule": SCHEDULE_LABELS["Non-Control"],
                "diagnosis":          random.choice(drug["diagnoses"]),
                "data_status":        "SIMULATED — TRAINING ONLY",
                "_sort_date":         fill_date,
            }
            records.append(rec)
            generated += 1

        return records

    # ------------------------------------------------------------------
    # Patient Management
    # ------------------------------------------------------------------

    def _get_or_create_patient(
        self,
        patients: Dict[int, Dict[str, Any]],
        drug: DrugDef,
        ref_date: date,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Either reuse an existing patient (simulating repeat fills)
        or create a new one.
        Returning patients = 60% of the time if pool is large enough.
        """
        if patients and len(patients) >= 5 and random.random() < 0.60:
            pat_id  = random.choice(list(patients.keys()))
            patient = patients[pat_id]
        else:
            pat_id  = len(patients) + 1
            patient = _generate_patient(pat_id, drug, ref_date)
            patients[pat_id] = patient

        return patient, pat_id

    # ------------------------------------------------------------------
    # Refill Logic
    # ------------------------------------------------------------------

    def _compute_refill_number(
        self,
        patient_id: int,
        drug: DrugDef,
        fill_date: date,
        fill_history: Dict,
    ) -> int:
        """
        Return the appropriate refill number for this fill.

        Logic:
          - First fill for this patient/drug → refill 0
          - Subsequent fills → increment (up to max_refills)
          - Fills must be at least 25 days apart to count as valid refill
        """
        history = fill_history[patient_id][drug["name"]]
        if not history:
            return 0

        # Count fills that are at least 25 days before this one
        prior_fills = [d for d in history if (fill_date - d).days >= 25]
        return min(len(prior_fills), drug["max_refills"])

    # ------------------------------------------------------------------
    # Prescriber Selection
    # ------------------------------------------------------------------

    def _build_specialty_index(self) -> None:
        """Index prescribers by specialty for efficient lookup."""
        self._specialty_index: Dict[str, List[Dict]] = defaultdict(list)
        for p in self.prescribers:
            spec = p.get("specialty", "Primary Care")
            self._specialty_index[spec].append(p)

    def _select_prescriber(
        self, drug: DrugDef, schedule: str
    ) -> Dict[str, Any]:
        """
        Select the most appropriate prescriber for this drug type.

        Matches on specialties defined in the drug's specialty list.
        Falls back to any available prescriber.
        """
        preferred_specs = drug.get("specialties", ["Primary Care"])

        # Try to find a prescriber with matching specialty
        candidates = []
        for spec in preferred_specs:
            candidates.extend(self._specialty_index.get(spec, []))

        if not candidates:
            # Fall back to full prescriber pool
            candidates = self.prescribers

        if not candidates:
            # Emergency fallback: generate a one-off prescriber
            return self._emergency_prescriber(drug)

        return random.choice(candidates)

    @staticmethod
    def _emergency_prescriber(drug: DrugDef) -> Dict[str, Any]:
        """Generate a minimal prescriber dict when pool is empty."""
        last_initial = random.choice("ABCDEFGHJKLMNPRSTUVWXYZ")
        return {
            "prescriber_name": f"Dr. John {random.choice(['Smith', 'Jones', 'Brown'])}",
            "dea_number":      generate_valid_dea("B", last_initial),
            "npi":             generate_valid_npi(),
            "specialty":       random.choice(drug.get("specialties", ["Primary Care"])),
            "zip":             "00000",
        }

    # ------------------------------------------------------------------
    # Payment Logic
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_payment(is_controlled: bool) -> Tuple[str, str]:
        """
        Return (payment_type, insurance_plan_name).
        Cash fills have empty insurance plan.
        """
        ratio = CASH_RATIO_CONTROLLED if is_controlled else CASH_RATIO_NON_CONTROLLED
        if random.random() < ratio:
            return "Cash", ""
        plan = random.choice(INSURANCE_PLANS)
        return "Insurance", plan

    # ------------------------------------------------------------------
    # Column Order
    # ------------------------------------------------------------------

    @staticmethod
    def _column_order() -> List[str]:
        return [
            "rx_number",
            "fill_date",
            "patient_name",
            "patient_dob",
            "patient_address",
            "patient_city",
            "patient_state",
            "patient_zip",
            "drug_name",
            "brand_name",
            "strength",
            "dosage_form",
            "quantity",
            "days_supply",
            "refill_number",
            "ndc",
            "ndc_labeler",
            "controlled_schedule",
            "prescriber_name",
            "prescriber_dea",
            "prescriber_npi",
            "prescriber_specialty",
            "prescriber_zip",
            "payment_type",
            "insurance_plan",
            "diagnosis",
            "data_status",
        ]
