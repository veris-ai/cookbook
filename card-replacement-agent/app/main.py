from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from agents import Runner, RunContextWrapper, trace

from .agent_setup.subagents import triage_agent
from .session_manager import SessionManager, BCSRunContext
from dotenv import load_dotenv
load_dotenv()

UI_DIR = Path(__file__).resolve().parent.parent / "ui" / "out"


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to send to the orchestrator agent")
    session_id: Optional[str] = Field(
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


app = FastAPI(title="Card Replacement Agent API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_session_manager(request: Request) -> SessionManager:
    """Provide the shared session manager instance."""

    return request.app.state.session_manager


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, session_manager: SessionManager = Depends(get_session_manager)) -> ChatResponse:
    session = await session_manager.get_session(req.session_id)
    async with session.run_lock:
        ctx = RunContextWrapper(BCSRunContext())
        with trace("Mini BCS workflow"):
            result = await Runner.run(
                triage_agent,
                input=req.message,
                context=ctx.context,
                session=session.agent_session,
            )
        tool_calls = list(ctx.context.tool_calls)

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
