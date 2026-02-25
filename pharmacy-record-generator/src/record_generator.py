"""
Core Pharmacy Dispensing Record Generator.

Generates clinically realistic simulated dispensing records for compliance
training, audit simulation, and internal testing purposes only.

Architecture:
  - Patient pool: generated once, reused across fills
  - Prescriber pool: from uploaded DEA file or auto-generated
  - Drug selection: weighted random, respecting controlled/non-controlled ratios
  - Fill spacing: tracks per-patient, per-drug fill dates to prevent unrealistic early fills
  - Date distribution: weighted toward weekdays with realistic daily volume
  - NDC lookup: delegated to NDCService with caching
"""

import logging
import random
from collections import defaultdict
from datetime import date, timedelta
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
    RX_BASE_MAX,
    RX_BASE_MIN,
    SCHEDULE_LABELS,
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
    # AL
    ("Birmingham",      "AL", "35201"), ("Montgomery",    "AL", "36101"),
    # AK
    ("Anchorage",       "AK", "99501"), ("Fairbanks",     "AK", "99701"),
    # AZ
    ("Phoenix",         "AZ", "85001"), ("Tucson",        "AZ", "85701"), ("Mesa",           "AZ", "85201"),
    # AR
    ("Little Rock",     "AR", "72201"), ("Fort Smith",    "AR", "72901"),
    # CA
    ("Los Angeles",     "CA", "90001"), ("San Francisco", "CA", "94102"), ("San Diego",      "CA", "92101"), ("Oakland",        "CA", "94601"),
    # CO
    ("Denver",          "CO", "80201"), ("Aurora",        "CO", "80010"), ("Colorado Springs","CO", "80901"),
    # CT
    ("Hartford",        "CT", "06101"), ("Bridgeport",    "CT", "06601"),
    # DE
    ("Wilmington",      "DE", "19801"), ("Dover",         "DE", "19901"),
    # FL
    ("Miami",           "FL", "33101"), ("Orlando",       "FL", "32801"), ("Tampa",          "FL", "33601"), ("Jacksonville",   "FL", "32201"),
    # GA
    ("Atlanta",         "GA", "30301"), ("Savannah",      "GA", "31401"), ("Augusta",        "GA", "30901"),
    # HI
    ("Honolulu",        "HI", "96801"), ("Hilo",          "HI", "96720"),
    # ID
    ("Boise",           "ID", "83701"), ("Nampa",         "ID", "83651"),
    # IL
    ("Chicago",         "IL", "60601"), ("Springfield",   "IL", "62701"), ("Rockford",       "IL", "61101"),
    # IN
    ("Indianapolis",    "IN", "46201"), ("Fort Wayne",    "IN", "46801"),
    # IA
    ("Des Moines",      "IA", "50301"), ("Cedar Rapids",  "IA", "52401"),
    # KS
    ("Wichita",         "KS", "67201"), ("Overland Park", "KS", "66210"),
    # KY
    ("Louisville",      "KY", "40201"), ("Lexington",     "KY", "40502"), ("Georgetown",     "KY", "40324"),
    # LA
    ("New Orleans",     "LA", "70112"), ("Baton Rouge",   "LA", "70801"), ("Shreveport",     "LA", "71101"),
    # ME
    ("Portland",        "ME", "04101"), ("Bangor",        "ME", "04401"),
    # MD
    ("Baltimore",       "MD", "21201"), ("Annapolis",     "MD", "21401"),
    # MA
    ("Boston",          "MA", "02101"), ("Worcester",     "MA", "01601"), ("Springfield",    "MA", "01101"),
    # MI
    ("Detroit",         "MI", "48201"), ("Grand Rapids",  "MI", "49501"), ("Lansing",        "MI", "48901"),
    # MN
    ("Minneapolis",     "MN", "55401"), ("Saint Paul",    "MN", "55101"), ("Rochester",      "MN", "55901"),
    # MS
    ("Jackson",         "MS", "39201"), ("Biloxi",        "MS", "39530"),
    # MO
    ("Kansas City",     "MO", "64101"), ("St. Louis",     "MO", "63101"), ("Columbia",       "MO", "65201"),
    # MT
    ("Billings",        "MT", "59101"), ("Missoula",      "MT", "59801"),
    # NE
    ("Omaha",           "NE", "68101"), ("Lincoln",       "NE", "68501"),
    # NV
    ("Las Vegas",       "NV", "89101"), ("Reno",          "NV", "89501"), ("Henderson",      "NV", "89002"),
    # NH
    ("Manchester",      "NH", "03101"), ("Concord",       "NH", "03301"),
    # NJ
    ("Newark",          "NJ", "07101"), ("Jersey City",   "NJ", "07301"), ("Trenton",        "NJ", "08601"),
    # NM
    ("Albuquerque",     "NM", "87101"), ("Santa Fe",      "NM", "87501"),
    # NY
    ("New York",        "NY", "10001"), ("Buffalo",       "NY", "14201"), ("Albany",         "NY", "12201"), ("Rochester",      "NY", "14601"),
    # NC
    ("Charlotte",       "NC", "28201"), ("Raleigh",       "NC", "27601"), ("Durham",         "NC", "27701"),
    # ND
    ("Fargo",           "ND", "58101"), ("Bismarck",      "ND", "58501"),
    # OH
    ("Columbus",        "OH", "43201"), ("Cleveland",     "OH", "44101"), ("Cincinnati",     "OH", "45201"),
    # OK
    ("Oklahoma City",   "OK", "73101"), ("Tulsa",         "OK", "74101"),
    # OR
    ("Portland",        "OR", "97201"), ("Salem",         "OR", "97301"), ("Eugene",         "OR", "97401"),
    # PA
    ("Philadelphia",    "PA", "19101"), ("Pittsburgh",    "PA", "15201"), ("Allentown",      "PA", "18101"),
    # RI
    ("Providence",      "RI", "02901"), ("Cranston",      "RI", "02910"),
    # SC
    ("Columbia",        "SC", "29201"), ("Greenville",    "SC", "29601"), ("Charleston",     "SC", "29401"),
    # SD
    ("Sioux Falls",     "SD", "57101"), ("Rapid City",    "SD", "57701"),
    # TN
    ("Nashville",       "TN", "37201"), ("Memphis",       "TN", "38101"), ("Franklin",       "TN", "37067"),
    # TX
    ("Houston",         "TX", "77001"), ("Dallas",        "TX", "75201"), ("San Antonio",    "TX", "78201"), ("Austin",         "TX", "78701"),
    # UT
    ("Salt Lake City",  "UT", "84101"), ("Provo",         "UT", "84601"),
    # VT
    ("Burlington",      "VT", "05401"), ("Montpelier",    "VT", "05601"),
    # VA
    ("Virginia Beach",  "VA", "23451"), ("Richmond",      "VA", "23220"), ("Roanoke",        "VA", "24001"),
    # WA
    ("Seattle",         "WA", "98101"), ("Spokane",       "WA", "99201"), ("Tacoma",         "WA", "98401"),
    # WV
    ("Charleston",      "WV", "25301"), ("Huntington",    "WV", "25701"),
    # WI
    ("Milwaukee",       "WI", "53201"), ("Madison",       "WI", "53703"), ("Green Bay",      "WI", "54301"),
    # WY
    ("Cheyenne",        "WY", "82001"), ("Casper",        "WY", "82601"),
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

def _generate_patient(
    patient_id: int,
    drug_def: DrugDef,
    ref_date: date,
    city_pool: Optional[List[Tuple]] = None,
) -> Dict[str, Any]:
    """Create a single patient record with demographics."""
    gender = random.choice(["M", "F"])
    first  = random.choice(_MALE_FIRST if gender == "M" else _FEMALE_FIRST)
    last   = random.choice(_LAST_NAMES)

    age_min, age_max = drug_def.get("patient_age_range", (18, 75))
    dob = _random_dob(age_min, age_max, ref_date)

    pool = city_pool if city_pool else _CITIES_STATES_ZIPS
    city, state, zip_code = random.choice(pool)
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
        target_state: Optional[str] = None,
    ) -> None:
        self.pharmacy      = pharmacy_config
        self.ndc_service   = ndc_service
        self.prescribers   = prescribers
        self.seed          = seed
        self.target_state  = target_state.upper().strip() if target_state else None

        if seed is not None:
            random.seed(seed)

        self._rx_counter  = random.randint(RX_BASE_MIN, RX_BASE_MAX)
        self._rx_gap_pool = [0, 0, 0, 1, 1, 2, 3]   # gaps between sequential RX numbers

        # Build city pool — filtered to target state when specified
        if self.target_state:
            filtered = [t for t in _CITIES_STATES_ZIPS if t[1] == self.target_state]
            self._city_pool = filtered if filtered else _CITIES_STATES_ZIPS
        else:
            self._city_pool = _CITIES_STATES_ZIPS

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

            # Acute meds (max_refills=0): enforce minimum 7-day spacing between fills
            if drug["max_refills"] == 0:
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
            patient = _generate_patient(pat_id, drug, ref_date, self._city_pool)
            patients[pat_id] = patient

        return patient, pat_id

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
