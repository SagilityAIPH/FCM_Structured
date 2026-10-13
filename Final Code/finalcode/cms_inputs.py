"""Pure CMS stage='all' input mapping; never imports live CMS automation."""
from .field_adapter import to_all_data


def to_cms_inputs(fields):
    """Return exactly the five CMS inputs, with names joined by one space.

    Keep legacy-key translation in the one-way adapter. In particular the CMS
    customer is Employer Name, never either customer-contact display label.
    """
    data = to_all_data(fields)
    return {key: data[key] for key in
            ("claimNumber", "claimID", "customer", "claimantFull", "referralType")}


def missing_cms_inputs(data):
    """Mirror run_flow's stage='all' check/order; referralType is optional."""
    return [key for key in ("claimNumber", "customer", "claimID", "claimantFull")
            if not str(data.get(key) or "").strip()]
