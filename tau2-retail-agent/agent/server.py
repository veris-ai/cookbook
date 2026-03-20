import os
from copy import deepcopy
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from tau2.agent.llm_agent import LLMAgentState
from tau2.data_model.message import ToolMessage, UserMessage
from tau2.domains.retail.data_model import RetailDB
from tau2.domains.retail.tools import RetailTools
from tau2.domains.retail.utils import RETAIL_DB_PATH, RETAIL_POLICY_PATH

from agent.tau2_agent import RetailAgent

LLM = os.environ.get("AGENT_LLM", "gpt-4.1-mini")

db = RetailDB.load(RETAIL_DB_PATH)
tools_instance = RetailTools(db)
tools_list = list(tools_instance.get_tools().values())
policy = RETAIL_POLICY_PATH.read_text()

agent = RetailAgent(
    tools=tools_list,
    domain_policy=policy,
    llm=LLM,
)

sessions: dict[str, LLMAgentState] = {}

app = FastAPI()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str


def _run_until_text(user_msg, state):
    msg, state = agent.generate_next_message(user_msg, state)

    while msg.tool_calls:
        for tc in msg.tool_calls:
            try:
                result = tools_instance.use_tool(tc.name, **tc.arguments)
                content = str(result)
                error = False
            except Exception as e:
                content = str(e)
                error = True
            tool_msg = ToolMessage(
                id=tc.id, role="tool", content=content, requestor="assistant", error=error
            )
            msg, state = agent.generate_next_message(tool_msg, state)

    return msg.content or "", state


@app.post("/chat")
def chat(req: ChatRequest):
    if req.session_id not in sessions:
        sessions[req.session_id] = agent.get_init_state()

    state = sessions[req.session_id]
    user_msg = UserMessage(content=req.message, role="user")
    response_text, state = _run_until_text(user_msg, state)
    sessions[req.session_id] = state

    return ChatResponse(response=response_text)
