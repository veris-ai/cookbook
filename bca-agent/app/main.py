import logging
import sys
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)

# Import eagerly so credential setup + agent wiring happens at startup
from app.services.bca_service import get_or_create_session, send_message  # noqa: E402

app = FastAPI(
    title="Banker Connections Agent",
    description="Clear CUID POC — resolves phone and ID update errors in Hogan",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request / Response schemas ---


class StartConversationRequest(BaseModel):
    banker_id: str
    branch_id: str
    customer_ecn: str


class StartConversationResponse(BaseModel):
    conversation_id: str
    status: str = "active"
    message: str


class SendMessageRequest(BaseModel):
    content: str
    timestamp: Optional[str] = None


class SendMessageResponse(BaseModel):
    message_id: str
    content: str
    action_required: str = "none"  # none | confirm_action | provide_info | escalated
    author: str = ""


class ConfirmActionRequest(BaseModel):
    action_id: str
    confirmed: bool


# --- Endpoints ---


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "bca-agent"}


@app.post("/api/v1/conversations", response_model=StartConversationResponse)
async def start_conversation(req: StartConversationRequest):
    """Start a new conversation with the Banker Connections Agent."""
    conversation_id = str(uuid.uuid4())

    # Create session with banker context
    await get_or_create_session(
        session_id=conversation_id,
        state={
            "banker_id": req.banker_id,
            "branch_id": req.branch_id,
            "customer_ecn": req.customer_ecn,
        },
    )

    # Send initial greeting by triggering the agent with a start message
    result = await send_message(
        session_id=conversation_id,
        message=f"I'm a banker (ID: {req.banker_id}) at branch {req.branch_id}. "
        f"I need help with customer ECN {req.customer_ecn}.",
    )

    return StartConversationResponse(
        conversation_id=conversation_id,
        status="active",
        message=result["content"],
    )


@app.post(
    "/api/v1/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
)
async def send_message_endpoint(conversation_id: str, req: SendMessageRequest):
    """Send a message in an existing conversation."""
    result = await send_message(
        session_id=conversation_id,
        message=req.content,
    )

    return SendMessageResponse(
        message_id=str(uuid.uuid4()),
        content=result["content"],
        action_required=result["action_required"],
        author=result["author"],
    )


@app.post(
    "/api/v1/conversations/{conversation_id}/confirm",
    response_model=SendMessageResponse,
)
async def confirm_action(conversation_id: str, req: ConfirmActionRequest):
    """Confirm or decline a proposed action."""
    if req.confirmed:
        message = "Yes, please proceed with the action."
    else:
        message = "No, do not proceed. Please escalate to a live agent."

    result = await send_message(
        session_id=conversation_id,
        message=message,
    )

    return SendMessageResponse(
        message_id=str(uuid.uuid4()),
        content=result["content"],
        action_required=result["action_required"],
        author=result["author"],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
