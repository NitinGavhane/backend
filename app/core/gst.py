"""Fixed GST configuration and place-of-supply logic.

The seller (admin) is always registered in West Bengal. The applicable tax is
decided automatically from the customer's order-address state — nothing is
configured per product:

  * customer in the seller's state  -> intra-state sale -> CGST + SGST
  * customer in any other state     -> inter-state sale -> IGST
"""

SELLER_STATE = "West Bengal"

CGST_PERCENTAGE = 9.0
SGST_PERCENTAGE = 9.0
IGST_PERCENTAGE = 18.0

# Accepted spellings/abbreviations for the seller's home state.
_SELLER_STATE_ALIASES = {"west bengal", "westbengal", "wb", "bengal"}

# GST two-digit state codes, keyed by state name (lower-cased). Used to render
# the "Place of Supply : <State> (<code>)" line on the tax invoice. Unknown
# states fall back to an empty code.
GST_STATE_CODES = {
    "jammu and kashmir": "01",
    "himachal pradesh": "02",
    "punjab": "03",
    "chandigarh": "04",
    "uttarakhand": "05",
    "haryana": "06",
    "delhi": "07",
    "rajasthan": "08",
    "uttar pradesh": "09",
    "bihar": "10",
    "sikkim": "11",
    "arunachal pradesh": "12",
    "nagaland": "13",
    "manipur": "14",
    "mizoram": "15",
    "tripura": "16",
    "meghalaya": "17",
    "assam": "18",
    "west bengal": "19",
    "jharkhand": "20",
    "odisha": "21",
    "orissa": "21",
    "chhattisgarh": "22",
    "madhya pradesh": "23",
    "gujarat": "24",
    "dadra and nagar haveli and daman and diu": "26",
    "daman and diu": "26",
    "dadra and nagar haveli": "26",
    "maharashtra": "27",
    "andhra pradesh": "28",
    "karnataka": "29",
    "goa": "30",
    "lakshadweep": "31",
    "kerala": "32",
    "tamil nadu": "33",
    "puducherry": "34",
    "andaman and nicobar islands": "35",
    "telangana": "36",
    "ladakh": "38",
    "other territory": "97",
}


def state_gst_code(state: str | None) -> str:
    """Two-digit GST state code for a state name, or '' when unknown."""
    return GST_STATE_CODES.get((state or "").strip().lower(), "")


def is_intra_state(customer_state: str | None) -> bool:
    """Return True for an intra-state sale (customer in the seller's state).

    Defaults to intra-state when the customer's state is unknown: the total GST
    is identical either way (CGST + SGST == IGST), only the split label differs.
    """
    normalized = (customer_state or "").strip().lower()
    if not normalized:
        return True
    return normalized in _SELLER_STATE_ALIASES


def gst_breakup(taxable_amount: float, customer_state: str | None) -> dict:
    """CGST/SGST/IGST amounts + total for a taxable amount and customer state."""
    if is_intra_state(customer_state):
        cgst = taxable_amount * CGST_PERCENTAGE / 100
        sgst = taxable_amount * SGST_PERCENTAGE / 100
        return {
            "cgst_amount": round(cgst, 2),
            "sgst_amount": round(sgst, 2),
            "igst_amount": 0.0,
            "gst_amount": round(cgst + sgst, 2),
        }
    igst = taxable_amount * IGST_PERCENTAGE / 100
    return {
        "cgst_amount": 0.0,
        "sgst_amount": 0.0,
        "igst_amount": round(igst, 2),
        "gst_amount": round(igst, 2),
    }
