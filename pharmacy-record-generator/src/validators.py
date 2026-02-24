"""
Validators for DEA numbers and NPI identifiers.

DEA Checksum Algorithm:
    Given a DEA number like AB1234563:
      - Letters: registrant type (A) + first letter of last name (B)
      - Digits: d1 d2 d3 d4 d5 d6 d7
      - odd_sum  = d1 + d3 + d5
      - even_sum = d2 + d4 + d6
      - checksum = odd_sum + 2 * even_sum
      - d7 must equal (checksum % 10)

NPI Luhn Checksum:
    Prepend "80840" to the 10-digit NPI, then apply the Luhn algorithm.
    The final digit of the NPI is the Luhn check digit.
"""

import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# DEA number pattern: 2 letters followed by 7 digits
_DEA_PATTERN = re.compile(r"^([A-Za-z]{2})(\d{7})$")

# Valid registrant type codes (first letter of DEA number)
_VALID_REGISTRANT_TYPES = set("ABCDEFGMPRSTUX")


# ---------------------------------------------------------------------------
# DEA Validation
# ---------------------------------------------------------------------------

def validate_dea(dea: str) -> Tuple[bool, str]:
    """
    Validate a DEA registration number.

    Returns
    -------
    (is_valid, message)
        is_valid : bool
        message  : human-readable description of the result
    """
    if not dea:
        return False, "DEA number is empty."

    dea = dea.strip().upper().replace("-", "").replace(" ", "")

    match = _DEA_PATTERN.match(dea)
    if not match:
        return False, f"Invalid format '{dea}'. Expected 2 letters + 7 digits (e.g. AB1234563)."

    letters, digits_str = match.group(1), match.group(2)

    # Validate registrant type (first letter)
    if letters[0] not in _VALID_REGISTRANT_TYPES:
        return (
            False,
            f"Invalid registrant type code '{letters[0]}'. "
            f"Valid codes: {', '.join(sorted(_VALID_REGISTRANT_TYPES))}.",
        )

    # Apply DEA checksum
    d = [int(c) for c in digits_str]
    odd_sum  = d[0] + d[2] + d[4]
    even_sum = d[1] + d[3] + d[5]
    checksum = (odd_sum + 2 * even_sum) % 10

    if checksum != d[6]:
        return (
            False,
            f"DEA checksum mismatch for '{dea}'. "
            f"Expected check digit {checksum}, found {d[6]}.",
        )

    return True, f"DEA number '{dea}' is valid."


def normalize_dea(dea: str) -> str:
    """Return uppercase, stripped DEA number."""
    return dea.strip().upper().replace("-", "").replace(" ", "")


def generate_valid_dea(registrant_type: str = "B", last_name_initial: str = "A") -> str:
    """
    Generate a syntactically valid DEA number for simulation purposes.

    Parameters
    ----------
    registrant_type   : str  — single letter from VALID_REGISTRANT_TYPES
    last_name_initial : str  — first letter of prescriber's last name
    """
    import random

    rt = registrant_type.upper()
    li = last_name_initial.upper()

    if rt not in _VALID_REGISTRANT_TYPES:
        rt = "B"
    if not li.isalpha():
        li = "A"

    # Generate 6 random digits then compute check digit
    d = [random.randint(0, 9) for _ in range(6)]
    odd_sum  = d[0] + d[2] + d[4]
    even_sum = d[1] + d[3] + d[5]
    check    = (odd_sum + 2 * even_sum) % 10
    digits   = "".join(str(x) for x in d) + str(check)
    return f"{rt}{li}{digits}"


# ---------------------------------------------------------------------------
# NPI Validation
# ---------------------------------------------------------------------------

def validate_npi(npi: str) -> Tuple[bool, str]:
    """
    Validate a National Provider Identifier (NPI) using the Luhn algorithm.

    The NPI Luhn check:
      1. Prepend the constant prefix "80840" to the 10-digit NPI.
      2. Apply the standard Luhn algorithm to the resulting 15-digit number.
      3. The result must be 0 (mod 10).

    Returns
    -------
    (is_valid, message)
    """
    if not npi:
        return False, "NPI is empty."

    npi = npi.strip().replace("-", "").replace(" ", "")

    if not npi.isdigit() or len(npi) != 10:
        return False, f"NPI '{npi}' must be exactly 10 digits."

    full_number = "80840" + npi
    total = 0
    reverse = full_number[::-1]

    for i, ch in enumerate(reverse):
        n = int(ch)
        if i % 2 == 1:          # double every second digit from the right
            n *= 2
            if n > 9:
                n -= 9
        total += n

    if total % 10 != 0:
        return False, f"NPI '{npi}' failed Luhn checksum."

    return True, f"NPI '{npi}' is valid."


def normalize_npi(npi: str) -> str:
    """Return digits-only NPI string."""
    return npi.strip().replace("-", "").replace(" ", "")


def generate_valid_npi() -> str:
    """
    Generate a syntactically valid 10-digit NPI for simulation purposes.
    Uses Luhn algorithm to compute the check digit.
    """
    import random

    # Generate 9 random digits (the 10th will be the Luhn check digit)
    base = [random.randint(0, 9) for _ in range(9)]
    prefix = [8, 0, 8, 4, 0]           # "80840"
    full = prefix + base + [0]          # placeholder for check digit

    # Compute Luhn check digit
    reverse = full[::-1]
    total = 0
    for i, n in enumerate(reverse[1:], start=1):   # skip index 0 (check digit placeholder)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n

    check = (10 - (total % 10)) % 10
    npi_digits = base + [check]
    return "".join(str(d) for d in npi_digits)


# ---------------------------------------------------------------------------
# Batch DEA Validation
# ---------------------------------------------------------------------------

def batch_validate_dea(dea_list: list) -> dict:
    """
    Validate a list of DEA numbers.

    Returns
    -------
    dict with keys:
        valid   : list of valid DEA strings
        invalid : list of dicts {dea, reason}
    """
    valid = []
    invalid = []
    seen = set()

    for raw_dea in dea_list:
        dea = normalize_dea(str(raw_dea))
        if dea in seen:
            continue                    # skip duplicate
        seen.add(dea)

        ok, msg = validate_dea(dea)
        if ok:
            valid.append(dea)
        else:
            invalid.append({"dea": dea, "reason": msg})

    return {"valid": valid, "invalid": invalid}
