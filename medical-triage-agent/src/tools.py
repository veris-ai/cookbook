"""PydanticAI tools for the triage agent — wrapping Epic FHIR and scheduling calls."""

import json
import logging
from typing import Any

from pydantic_ai import RunContext

import fhir_client
import scheduling_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FHIR tools
# ---------------------------------------------------------------------------


async def search_patient(ctx: RunContext, name: str = "", mrn: str = "") -> str:
    """Search for a patient by name or MRN.

    Args:
        name: Patient name (partial match supported, e.g. "Emma" or "Johnson").
        mrn: Medical Record Number for exact lookup (e.g. "MRN-10234").
    """
    results = await fhir_client.search_patient(name=name, mrn=mrn)
    if not results:
        return "No patients found matching the search criteria."
    return json.dumps(results, indent=2, default=str)


async def get_patient_record(ctx: RunContext, patient_id: str) -> str:
    """Get the full demographic record for a patient by their FHIR resource ID.

    Args:
        patient_id: The FHIR Patient resource ID.
    """
    patient = await fhir_client.get_patient(patient_id)
    if not patient:
        return f"Patient {patient_id} not found."
    return json.dumps(patient, indent=2, default=str)


async def get_patient_conditions(ctx: RunContext, patient_id: str) -> str:
    """Get active medical conditions and diagnoses for a patient.

    Use this to understand the patient's current health issues and
    pre-existing conditions before making a triage recommendation.

    Args:
        patient_id: The FHIR Patient resource ID.
    """
    conditions = await fhir_client.get_conditions(patient_id)
    if not conditions:
        return f"No active conditions found for patient {patient_id}."
    return json.dumps(conditions, indent=2, default=str)


async def get_patient_allergies(ctx: RunContext, patient_id: str) -> str:
    """Get known allergies and intolerances for a patient.

    Important for safe referral — some specialists need to know about
    drug allergies before prescribing treatment.

    Args:
        patient_id: The FHIR Patient resource ID.
    """
    allergies = await fhir_client.get_allergies(patient_id)
    if not allergies:
        return f"No allergies recorded for patient {patient_id}."
    return json.dumps(allergies, indent=2, default=str)


async def get_patient_immunizations(ctx: RunContext, patient_id: str) -> str:
    """Get immunization history for a patient.

    Useful for checking vaccination status when symptoms may relate to
    vaccine-preventable diseases.

    Args:
        patient_id: The FHIR Patient resource ID.
    """
    immunizations = await fhir_client.get_immunizations(patient_id)
    if not immunizations:
        return f"No immunization records found for patient {patient_id}."
    return json.dumps(immunizations, indent=2, default=str)


async def get_patient_vitals(ctx: RunContext, patient_id: str) -> str:
    """Get recent vital signs for a patient (temperature, heart rate, BP, etc.).

    Use this to check for fever, abnormal heart rate, or other signs that
    may indicate urgency or help narrow the triage recommendation.

    Args:
        patient_id: The FHIR Patient resource ID.
    """
    vitals = await fhir_client.get_vitals(patient_id)
    if not vitals:
        return f"No recent vitals found for patient {patient_id}."
    return json.dumps(vitals, indent=2, default=str)


async def get_patient_medications(ctx: RunContext, patient_id: str) -> str:
    """Get active medications for a patient.

    Important for checking drug interactions and contraindications before
    referring to a specialist who may prescribe new medications.

    Args:
        patient_id: The FHIR Patient resource ID.
    """
    medications = await fhir_client.get_medications(patient_id)
    if not medications:
        return f"No active medications found for patient {patient_id}."
    return json.dumps(medications, indent=2, default=str)


# ---------------------------------------------------------------------------
# Scheduling tools
# ---------------------------------------------------------------------------


async def check_specialist_availability(
    ctx: RunContext,
    specialty: str,
    days_ahead: int = 14,
) -> str:
    """Check available appointment slots for a specialist via FHIR Slot resource.

    Use this after recommending a specialist to find available times.

    Args:
        specialty: The specialty to search for (e.g. "Cardiology", "Neurology").
        days_ahead: How many days ahead to search (default 14).
    """
    slots = await scheduling_client.check_availability(
        specialty=specialty, days_ahead=days_ahead
    )
    if not slots:
        return f"No available slots found for {specialty} in the next {days_ahead} days."
    return json.dumps(slots, indent=2, default=str)


async def book_referral_appointment(
    ctx: RunContext,
    patient_id: str,
    slot_id: str,
    reason: str,
    urgency: str = "routine",
) -> str:
    """Book a referral appointment via FHIR Appointment resource.

    Only call this after confirming the appointment details with the caller.

    Args:
        patient_id: The FHIR Patient resource ID.
        slot_id: The Slot resource ID from check_specialist_availability results.
        reason: Brief referral reason (e.g. "Recurring migraines, needs neurological evaluation").
        urgency: "routine", "urgent", or "emergent".
    """
    result = await scheduling_client.book_appointment(
        patient_id=patient_id,
        slot_id=slot_id,
        reason=reason,
        urgency=urgency,
    )
    return json.dumps(result, indent=2, default=str)
