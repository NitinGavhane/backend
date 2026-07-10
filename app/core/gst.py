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
