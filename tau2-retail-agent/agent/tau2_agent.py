from typing import List, Optional

from tau2.agent.llm_agent import LLMAgent, LLMAgentState
from tau2.data_model.message import Message, SystemMessage
from tau2.agent.base import is_valid_agent_history_message
from tau2.environment.tool import Tool

from agent.core import build_system_prompt


class RetailAgent(LLMAgent):
    def __init__(
        self,
        tools: List[Tool],
        domain_policy: str,
        llm: Optional[str] = None,
        llm_args: Optional[dict] = None,
    ):
        super().__init__(
            tools=tools,
            domain_policy=domain_policy,
            llm=llm,
            llm_args=llm_args,
        )

    @property
    def system_prompt(self) -> str:
        return build_system_prompt(self.domain_policy)

    def get_init_state(
        self, message_history: Optional[list[Message]] = None
    ) -> LLMAgentState:
        if message_history is None:
            message_history = []
        assert all(is_valid_agent_history_message(m) for m in message_history)
        return LLMAgentState(
            system_messages=[SystemMessage(role="system", content=self.system_prompt)],
            messages=message_history,
        )
