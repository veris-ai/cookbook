"""Hogan API tools for Google ADK agents.

These tools wrap the simulated Hogan CIS API for customer profile
inquiry and update (clear CUID) operations.
"""

import logging
from typing import Optional

import httpx
from google.adk.tools import ToolContext

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_client = httpx.AsyncClient(
    base_url=settings.hogan_api_base_url,
    auth=(
        (settings.hogan_api_username, settings.hogan_api_password)
        if settings.hogan_api_username
        else None
    ),
    timeout=30.0,
)


async def hogan_get_customer(
    input_key: str,
    company_nbr: Optional[int] = None,
    tie: Optional[int] = None,
    tool_context: ToolContext = None,
) -> dict:
    """Look up a customer profile from the Hogan CIS system.

    Use this tool to retrieve the customer's current data before making any
    updates. You MUST call this before any update to get the required fields
    (companyNbr, customerNameLine1, birthDt, genderCd,
    customerOfficer1Cd, customerOfficer2Cd).

    Note: customerTie is NOT returned in GET responses. For ECN or
    customer-number lookups, use the default of 0 when calling
    hogan_update_customer.

    Note: sensitivityCode is NOT returned in GET responses. It is only
    available in PATCH responses. Pass it to hogan_update_customer only if
    you have it from a previous PATCH call; otherwise omit it.

    Args:
        input_key: Customer identifier — can be a customer number, name, or SSN/Tax ID.
        company_nbr: Optional company number of the customer.
        tie: Optional tie breaker — mandatory if customer name is used as input_key.

    Returns:
        Customer profile data including phone numbers, ID documents, and all
        required fields for subsequent PATCH operations.
    """
    params = {}
    if company_nbr is not None:
        params["companyNbr"] = company_nbr
    if tie is not None:
        params["tie"] = tie

    try:
        response = await _client.get(f"/customers/{input_key}", params=params)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Hogan GET /customers/{input_key} — success")
        return {"status": "success", "customer": data}
    except httpx.HTTPStatusError as e:
        logger.error(f"Hogan GET /customers/{input_key} — HTTP {e.response.status_code}")
        return {
            "status": "error",
            "error": f"HTTP {e.response.status_code}: {e.response.text}",
        }
    except Exception as e:
        logger.error(f"Hogan GET /customers/{input_key} — {e}")
        return {"status": "error", "error": "Hogan system is currently unavailable. Please try again later."}


async def hogan_update_customer(
    input_key: str,
    company_nbr: int,
    customer_name_line1: str,
    birth_dt: str,
    gender_cd: str,
    customer_officer1_cd: str,
    customer_officer2_cd: str,
    customer_tie: int = 0,
    sensitivity_code: Optional[int] = None,
    home_phone_nbr: Optional[str] = None,
    business_phone_nbr: Optional[str] = None,
    document_type: Optional[str] = None,
    document_nbr: Optional[str] = None,
    document_issue_dt: Optional[str] = None,
    document_issue_place: Optional[str] = None,
    personal_id: Optional[str] = None,
    tool_context: ToolContext = None,
) -> dict:
    """Update (clear/modify) a customer profile in the Hogan CIS system.

    Use this tool to clear phone or ID fields to resolve CUID errors.
    To clear a field, pass an empty string for it.

    You MUST first call hogan_get_customer to retrieve the required fields.
    All required fields must be provided even if you are only clearing phone data.

    Args:
        input_key: Customer identifier (customer number, name, or SSN).
        company_nbr: Company number (required, from GET response).
        customer_name_line1: Customer name line 1 (required, from GET response).
        birth_dt: Birth date YYYY-MM-DD (required, from GET response).
        gender_cd: Gender code (required, from GET response).
        customer_officer1_cd: Primary officer code (required, from GET response).
        customer_officer2_cd: Secondary officer code (required, from GET response).
        customer_tie: Tie breaker — defaults to 0 for ECN/customer-number lookups. Only needed for name-based lookups.
        sensitivity_code: Sensitivity code 0-9 (optional — not in GET response, only in PATCH response).
        home_phone_nbr: Home phone — send empty string "" to clear.
        business_phone_nbr: Business phone — send empty string "" to clear.
        document_type: ID document type — send empty string "" to clear.
        document_nbr: ID document number — send empty string "" to clear.
        document_issue_dt: ID issue date — send empty string "" to clear.
        document_issue_place: ID issue place — send empty string "" to clear.
        personal_id: Personal ID — send empty string "" to clear.

    Returns:
        Updated customer profile data confirming the changes.
    """
    body: dict = {
        "companyNbr": company_nbr,
        "inputKey": input_key,
        "customerTie": customer_tie,
        "customerNameLine1": customer_name_line1,
        "birthDt": birth_dt,
        "genderCd": gender_cd,
        "customerOfficer1Cd": customer_officer1_cd,
        "customerOfficer2Cd": customer_officer2_cd,
    }
    if sensitivity_code is not None:
        body["sensitivityCode"] = sensitivity_code

    # Only include optional fields that were explicitly provided
    if home_phone_nbr is not None:
        body["homePhoneNbr"] = home_phone_nbr
    if business_phone_nbr is not None:
        body["businessPhoneNbr"] = business_phone_nbr
    if document_type is not None:
        body["documentType"] = document_type
    if document_nbr is not None:
        body["documentNbr"] = document_nbr
    if document_issue_dt is not None:
        body["documentIssueDt"] = document_issue_dt
    if document_issue_place is not None:
        body["documentIssuePlace"] = document_issue_place
    if personal_id is not None:
        body["personalId"] = personal_id

    try:
        response = await _client.patch(f"/customers/{input_key}", json=body)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Hogan PATCH /customers/{input_key} — success")
        return {"status": "success", "customer": data}
    except httpx.HTTPStatusError as e:
        logger.error(f"Hogan PATCH /customers/{input_key} — HTTP {e.response.status_code}")
        return {
            "status": "error",
            "error": f"HTTP {e.response.status_code}: {e.response.text}",
        }
    except Exception as e:
        logger.error(f"Hogan PATCH /customers/{input_key} — {e}")
        return {"status": "error", "error": "Hogan system is currently unavailable. Please try again later."}
