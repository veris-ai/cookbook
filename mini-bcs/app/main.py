from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Dict, Any
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from agents import Runner, RunContextWrapper, trace
from agents.items import ToolCallItem, ToolCallOutputItem
from .agent_setup.subagents import credit_card_agent
from .session_manager import SessionManager, BCSRunContext
from dotenv import load_dotenv

load_dotenv()

UI_DIR = Path(__file__).resolve().parent.parent / "ui" / "out"

class ChatRequest(BaseModel):
    message: str = Field(..., description="Message to send to the mini-bcs agent.")
    session_id: str | None = Field(
        default=None,
        description="Existing session identifier to continue a prior conversation.",
    )


class ChatResponse(BaseModel):
    session_id: str
    response: str
    tool_calls: List[Dict[str, Any]]
    data: Dict[str, Any]

@asynccontextmanager
async def lifespan(app: FastAPI):
    session_manager = SessionManager()
    app.state.session_manager = session_manager
    try:
        yield
    finally:
        await session_manager.close()


app = FastAPI(title="mini_bcs API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.session_manager


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse, operation_id="send_chat_message")
async def chat(
    req: ChatRequest,
    session_manager: SessionManager = Depends(get_session_manager),
) -> ChatResponse:
    session = await session_manager.get_session(req.session_id)
    async with session.run_lock:
        ctx = RunContextWrapper(BCSRunContext())

        with trace("Mini BCS workflow"):
            result = await Runner.run(
                credit_card_agent,
                input=req.message,
                context=ctx.context,
                session=session.agent_session,
            )
        tool_calls = []
        for item in result.new_items:
            if isinstance(item, ToolCallItem):
                raw = item.raw_item
                tool_calls.append({
                    "type": "call",
                    "name": raw.get("name", "") if isinstance(raw, dict) else getattr(raw, "name", ""),
                    "arguments": raw.get("arguments", "") if isinstance(raw, dict) else getattr(raw, "arguments", ""),
                })
            elif isinstance(item, ToolCallOutputItem):
                tool_calls.append({
                    "type": "output",
                    "output": str(item.output),
                })

        data = dict(ctx.context.data)
        session.touch()
    return ChatResponse(
        session_id=session.session_id,
        response=result.final_output,
        tool_calls=tool_calls,
        data=data,
    )

# Serve the Next.js static export if it exists
if UI_DIR.is_dir():
    @app.get("/")
    async def serve_index():
        return FileResponse(UI_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(UI_DIR)), name="ui")
