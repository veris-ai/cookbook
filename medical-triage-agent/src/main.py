"""Medical Triage Agent — PydanticAI on AgentCore."""

import json
import logging
import os
import sys
from pathlib import Path

# Ensure src/ is on the Python path so sibling modules resolve
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider

from tools import (
    book_referral_appointment,
    check_specialist_availability,
    get_patient_allergies,
    get_patient_conditions,
    get_patient_immunizations,
    get_patient_medications,
    get_patient_record,
    get_patient_vitals,
    search_patient,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
_bedrock_model_id = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")

model = BedrockConverseModel(
    _bedrock_model_id,
    provider=BedrockProvider(
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    ),
)

# ---------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------
instructions = """\
You are a medical triage assistant. You help refer patients to the \
appropriate specialist through conversation. You have access to an Epic \
FHIR API to look up patient records.

## Workflow

1. **Identify the patient.** Ask for the patient's name or MRN, then use \
   `search_patient` to look them up. If multiple matches, ask the caller \
   to confirm which patient.
2. **Gather symptoms.** Ask the patient or their representative to describe:
   - Chief complaint (main reason for the visit)
   - Duration and severity of symptoms
   - Any recent changes or triggers
3. **Review the chart.** Use the FHIR tools to pull:
   - Active conditions (`get_patient_conditions`)
   - Allergies (`get_patient_allergies`)
   - Active medications (`get_patient_medications`)
   - Recent vitals (`get_patient_vitals`)
   - Immunization status if relevant (`get_patient_immunizations`)
4. **Recommend a specialist.** Based on symptoms and chart data, recommend \
   one of the following specialists:
   - **Cardiologist** — chest pain, heart murmur, palpitations, cyanosis, syncope
   - **Neurologist** — seizures, recurring headaches/migraines, developmental \
     delays, tics, numbness
   - **Pulmonologist** — chronic cough, asthma exacerbation, wheezing, \
     recurrent pneumonia, breathing difficulties
   - **Gastroenterologist** — chronic abdominal pain, GERD, persistent \
     vomiting/diarrhea, failure to thrive, GI bleeding
   - **Allergist/Immunologist** — recurrent allergic reactions, suspected \
     food allergies, chronic urticaria, immunodeficiency
   - **Dermatologist** — persistent rashes, eczema flares, unusual skin \
     lesions, concerning moles
   - **Orthopedist** — scoliosis, fractures, limping, joint pain, \
     musculoskeletal deformities
   - **ENT (Otolaryngologist)** — recurrent ear infections, tonsillitis, \
     hearing loss, nasal obstruction, sleep apnea
   - **Endocrinologist** — growth concerns, diabetes, thyroid issues, \
     hormonal imbalances
   - **General Practitioner** — routine care, mild illness, wellness visit, \
     anything not clearly requiring a specialist
5. **Summarize.** Provide a brief triage summary including:
   - Patient name and age
   - Chief complaint
   - Relevant findings from the chart (conditions, allergies, abnormal vitals)
   - Recommended specialist and reasoning
   - Urgency level: **Routine**, **Urgent**, or **Emergent**

## Guidelines
- Always check for drug allergies and active medications before referral.
- Flag any vital signs outside normal ranges.
- If symptoms suggest an emergency (difficulty breathing, altered \
  consciousness, severe dehydration, chest pain with hemodynamic instability), \
  advise going to the ER immediately rather than a specialist referral.
- Be conversational and empathetic.
- If you do not have enough information to make a recommendation, ask \
  follow-up questions rather than guessing.

## Scheduling
After making a recommendation, offer to check specialist availability \
using `check_specialist_availability`. If the caller confirms, book the \
appointment with `book_referral_appointment`. Always confirm details \
(specialist, time, reason) before booking.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = Agent(
    model,
    system_prompt=instructions,
    tools=[
        search_patient,
        get_patient_record,
        get_patient_conditions,
        get_patient_allergies,
        get_patient_medications,
        get_patient_immunizations,
        get_patient_vitals,
        check_specialist_availability,
        book_referral_appointment,
    ],
)

# ---------------------------------------------------------------------------
# AgentCore app
# ---------------------------------------------------------------------------
app = BedrockAgentCoreApp()

# In-memory conversation histories keyed by session ID.
# In production, replace with AgentCore MemorySessionManager for persistence.
_sessions: dict[str, list[ModelMessage]] = {}


@app.entrypoint
async def invoke(payload: dict, context) -> dict:
    """Single-turn invocation (also used as fallback for non-WebSocket clients)."""
    session_id = context.session_id
    history = _sessions.get(session_id, []) if session_id else []

    result = await agent.run(payload.get("prompt", ""), message_history=history)

    if session_id:
        _sessions[session_id] = list(result.all_messages())

    return {"response": result.output}


@app.websocket
async def websocket_handler(websocket, context):
    """Multi-turn WebSocket handler for conversational triage."""
    await websocket.accept()

    session_id = context.session_id or str(id(websocket))
    if session_id not in _sessions:
        _sessions[session_id] = []

    logger.info("WebSocket session started: %s", session_id)

    try:
        while True:
            data = await websocket.receive_text()
            logger.info("Session %s raw data: %s", session_id, data[:200])

            try:
                message = json.loads(data)
                user_input = message.get("inputText", message.get("prompt", message.get("message", "")))
            except json.JSONDecodeError:
                user_input = data

            if not user_input or not user_input.strip():
                await websocket.send_text(json.dumps({"error": "No input provided"}))
                continue

            logger.info("Session %s received: %s", session_id, user_input[:100])

            try:
                history = _sessions[session_id]
                result = await agent.run(user_input, message_history=history)
                _sessions[session_id] = list(result.all_messages())
                response = result.output
            except Exception as e:
                logger.error("Agent error in session %s: %s", session_id, str(e), exc_info=True)
                response = f"I encountered an error processing your request: {str(e)}"

            logger.info("Session %s responding: %s", session_id, response[:100])
            await websocket.send_text(response)

    except Exception as e:
        logger.info("WebSocket session ended: %s (%s)", session_id, type(e).__name__)


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8088")))
