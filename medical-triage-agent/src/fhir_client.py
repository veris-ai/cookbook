"""Epic FHIR R4 client for patient data.

Uses the fhirclient SDK for proper FHIR resource handling and search semantics.
"""

import asyncio
import logging
import os
from typing import Any

from fhirclient import client
from fhirclient.models.allergyintolerance import AllergyIntolerance
from fhirclient.models.condition import Condition
from fhirclient.models.immunization import Immunization
from fhirclient.models.medicationrequest import MedicationRequest
from fhirclient.models.observation import Observation
from fhirclient.models.patient import Patient

logger = logging.getLogger(__name__)


def _get_smart_client() -> client.FHIRClient:
    """Create a FHIRClient configured from environment variables."""
    settings = {
        "app_id": "medical-triage-agent",
        "api_base": os.getenv("FHIR_BASE_URL", "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"),
    }
    smart = client.FHIRClient(settings=settings)

    # Inject bearer token via the requests session headers
    token = os.getenv("FHIR_TOKEN", "")
    if token:
        smart.server.session.headers.update({"Authorization": f"Bearer {token}"})

    return smart


def _resource_to_dict(resource) -> dict[str, Any]:
    """Convert a FHIR resource to a JSON-serializable dict."""
    return resource.as_json()


# ---------------------------------------------------------------------------
# Public API — all async, wrapping sync fhirclient calls
# ---------------------------------------------------------------------------


async def search_patient(name: str = "", mrn: str = "") -> list[dict[str, Any]]:
    """Search for a patient by name or MRN.

    Uses: GET /Patient?name={name} or GET /Patient?identifier={mrn}
    """
    if not name and not mrn:
        return []

    def _search():
        smart = _get_smart_client()
        params = {}
        if mrn:
            params["identifier"] = mrn
        elif name:
            params["name"] = name

        search = Patient.where(struct=params)
        results = search.perform_resources(smart.server)
        return [_resource_to_dict(r) for r in results]

    return await asyncio.to_thread(_search)


async def get_patient(patient_id: str) -> dict[str, Any] | None:
    """Get a patient by FHIR resource ID.

    Uses: GET /Patient/{id}
    """
    def _read():
        smart = _get_smart_client()
        try:
            patient = Patient.read(patient_id, smart.server)
            return _resource_to_dict(patient)
        except Exception:
            return None

    return await asyncio.to_thread(_read)


async def get_conditions(patient_id: str) -> list[dict[str, Any]]:
    """Get active conditions for a patient.

    Uses: GET /Condition?patient={id}&clinical-status=active
    """
    def _search():
        smart = _get_smart_client()
        search = Condition.where(struct={
            "patient": patient_id,
            "clinical-status": "active",
        })
        results = search.perform_resources(smart.server)
        return [_resource_to_dict(r) for r in results]

    return await asyncio.to_thread(_search)


async def get_allergies(patient_id: str) -> list[dict[str, Any]]:
    """Get allergy intolerances for a patient.

    Uses: GET /AllergyIntolerance?patient={id}
    """
    def _search():
        smart = _get_smart_client()
        search = AllergyIntolerance.where(struct={"patient": patient_id})
        results = search.perform_resources(smart.server)
        return [_resource_to_dict(r) for r in results]

    return await asyncio.to_thread(_search)


async def get_immunizations(patient_id: str) -> list[dict[str, Any]]:
    """Get immunization history for a patient.

    Uses: GET /Immunization?patient={id}
    """
    def _search():
        smart = _get_smart_client()
        search = Immunization.where(struct={"patient": patient_id})
        results = search.perform_resources(smart.server)
        return [_resource_to_dict(r) for r in results]

    return await asyncio.to_thread(_search)


async def get_vitals(patient_id: str) -> list[dict[str, Any]]:
    """Get recent vital signs for a patient.

    Uses: GET /Observation?patient={id}&category=vital-signs&_sort=-date&_count=10
    """
    def _search():
        smart = _get_smart_client()
        search = Observation.where(struct={
            "patient": patient_id,
            "category": "vital-signs",
            "_sort": "-date",
            "_count": "10",
        })
        results = search.perform_resources(smart.server)
        return [_resource_to_dict(r) for r in results]

    return await asyncio.to_thread(_search)


async def get_medications(patient_id: str) -> list[dict[str, Any]]:
    """Get active medication requests for a patient.

    Uses: GET /MedicationRequest?patient={id}&status=active
    """
    def _search():
        smart = _get_smart_client()
        search = MedicationRequest.where(struct={
            "patient": patient_id,
            "status": "active",
        })
        results = search.perform_resources(smart.server)
        return [_resource_to_dict(r) for r in results]

    return await asyncio.to_thread(_search)
