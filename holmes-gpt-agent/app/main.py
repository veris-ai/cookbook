import json
import logging
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from . import process_chat_streaming

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="HolmesGPT — PagerDuty SRE Agent")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(req: ChatRequest) -> dict[str, Any]:
    """Single-turn HTTP — drains the stream and returns the final analysis."""
    final: dict[str, Any] = {"events": []}
    async for event in process_chat_streaming(req.message):
        final["events"].append(event.model_dump())
        if event.type in {"done", "error"}:
            final["status"] = event.type
            final["content"] = event.content
            final["metadata"] = event.metadata
    return final


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                parsed = json.loads(data)
                user_message = parsed.get("message", "")
            except json.JSONDecodeError:
                user_message = data

            if not user_message or not user_message.strip():
                await websocket.send_json({
                    "type": "error",
                    "content": "No message provided",
                    "metadata": {},
                })
                continue

            async for event in process_chat_streaming(user_message):
                await websocket.send_json(event.model_dump())

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
