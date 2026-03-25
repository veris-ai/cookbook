"""Scheduling via Epic FHIR R4 — Slot and Appointment resources.

Uses the fhirclient SDK for proper FHIR resource handling.
"""

import asyncio
import logging
import os
from typing import Any

from fhirclient import client
from fhirclient.models.appointment import Appointment, AppointmentParticipant
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.slot import Slot

logger = logging.getLogger(__name__)


def _get_smart_client() -> client.FHIRClient:
    """Create a FHIRClient configured from environment variables."""
    settings = {
        "app_id": "medical-triage-agent",
        "api_base": os.getenv("FHIR_BASE_URL", "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"),
    }
    smart = client.FHIRClient(settings=settings)

    token = os.getenv("FHIR_TOKEN", "")
    if token:
        smart.server.session.headers.update({"Authorization": f"Bearer {token}"})

    return smart


def _resource_to_dict(resource) -> dict[str, Any]:
    """Convert a FHIR resource to a JSON-serializable dict."""
    return resource.as_json()


async def check_availability(
    specialty: str,
    days_ahead: int = 14,
) -> list[dict[str, Any]]:
    """Search for available Slots by specialty.

    Uses: GET /Slot?specialty={specialty}&status=free&_count=10
    """
    def _search():
        smart = _get_smart_client()
        search = Slot.where(struct={
            "specialty": specialty,
            "status": "free",
            "_count": "10",
        })
        results = search.perform_resources(smart.server)
        return [_resource_to_dict(r) for r in results]

    return await asyncio.to_thread(_search)


async def book_appointment(
    patient_id: str,
    slot_id: str,
    reason: str,
    urgency: str = "routine",
) -> dict[str, Any]:
    """Create an Appointment resource to book a referral.

    Uses: POST /Appointment
    """
    priority_map = {"routine": 5, "urgent": 2, "emergent": 1}

    def _create():
        smart = _get_smart_client()

        appointment = Appointment()
        appointment.status = "booked"
        appointment.priority = priority_map.get(urgency, 5)
        appointment.description = reason

        slot_ref = FHIRReference()
        slot_ref.reference = f"Slot/{slot_id}"
        appointment.slot = [slot_ref]

        patient_ref = FHIRReference()
        patient_ref.reference = f"Patient/{patient_id}"
        participant = AppointmentParticipant()
        participant.actor = patient_ref
        participant.status = "accepted"
        appointment.participant = [participant]

        result = appointment.create(smart.server)
        return result.as_json() if hasattr(result, "as_json") else result

    return await asyncio.to_thread(_create)
