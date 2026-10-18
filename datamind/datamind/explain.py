"""DataMind: Number verification and grounding engine."""

import re
from typing import Any, List


def extract_numbers(text: str) -> List[str]:
    """Extract candidate numeric sequences from a string, stripping currencies and commas."""
    # Matches integers, decimals, percentages, currency amounts
    raw_matches = re.findall(r"(?:[\$€£])?\b\d+(?:,\d{3})*(?:\.\d+)?%?\b", text)
    cleaned = []
    for m in raw_matches:
        # Strip currency symbols, percentages, and trailing dots
        c = m.replace("$", "").replace("€", "").replace("£", "").replace("%", "").replace(",", "").rstrip(".")
        if c:
            cleaned.append(c)
    return cleaned


def numbers_grounded(answer: str, rows: List[List[Any]]) -> bool:
    """
    Verify whether every numeric claim in the model's answer is grounded in the retrieved rows.
    Returns True if grounded, False if an unverified number is detected.
    """
    if not rows:
        # If no rows, answer shouldn't assert positive data numbers
        nums = extract_numbers(answer)
        # 0 or no numbers is acceptable for empty rows
        return len(nums) == 0 or all(n == "0" for n in nums)

    # Flatten row values into both text representation and float set for robust matching
    cell_strings = []
    numeric_floats = set()

    for r in rows:
        for cell in r:
            if cell is not None:
                s = str(cell).replace(",", "")
                cell_strings.append(s)
                try:
                    numeric_floats.add(round(float(s), 4))
                except (ValueError, TypeError):
                    pass

    cell_corpus = " ".join(cell_strings)
    answer_numbers = extract_numbers(answer)

    for num_str in answer_numbers:
        # Check direct substring match
        if num_str in cell_corpus:
            continue

        # Check numeric float equivalence
        try:
            val = round(float(num_str), 4)
            # Allow common rank numbers like 1, 2, 3 if within row length
            if val.is_integer() and 1 <= int(val) <= max(10, len(rows)):
                continue
            if val in numeric_floats:
                continue
        except (ValueError, TypeError):
            pass

        # Number could not be grounded in rows
        return False

    return True
