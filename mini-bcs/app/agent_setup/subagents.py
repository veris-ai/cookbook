import os
import logging
from openai import AsyncOpenAI, AsyncAzureOpenAI
from agents import Agent, RunContextWrapper, OpenAIChatCompletionsModel, set_default_openai_api
from .agent_tools import (
    change_card_status,
    display_card_info_by_last4,
    display_user_info,
    request_card_replacement,
    update_card_replacement_status,
)

logger = logging.getLogger(__name__)
set_default_openai_api("chat_completions")

with open("agent_desc.txt", "r") as f:
    agent_desc = f.read()


def get_model():
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    logger.info(f"LLM_PROVIDER={provider}")

    if provider in ("baseten", "deepseek"):
        base_url = os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1")
        model_name = os.getenv("BASETEN_MODEL", "deepseek-ai/DeepSeek-V3.2")
        logger.info(f"Using Baseten/DeepSeek: model={model_name}")
        client = AsyncOpenAI(api_key=os.getenv("BASETEN_API_KEY"), base_url=base_url)
        return OpenAIChatCompletionsModel(model=model_name, openai_client=client)

    if provider in ("gpt-oss", "gptoss"):
        model_name = "openai/gpt-oss-120b"
        logger.info(f"Using GPT-OSS: model={model_name}")
        client = AsyncOpenAI(api_key=os.getenv("BASETEN_API_KEY"), base_url="https://inference.baseten.co/v1")
        return OpenAIChatCompletionsModel(model=model_name, openai_client=client)

    if provider in ("xai", "grok"):
        model_name = os.getenv("XAI_MODEL", "grok-3-fast")
        logger.info(f"Using xAI/Grok: model={model_name}")
        client = AsyncOpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")
        return OpenAIChatCompletionsModel(model=model_name, openai_client=client)

    if provider in ("azure", "azure-openai"):
        model_name = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o").replace("azure/", "")
        logger.info(f"Using Azure OpenAI: model={model_name}")
        client = AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_API_KEY"),
            api_version=os.getenv("AZURE_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_API_BASE"),
        )
        return OpenAIChatCompletionsModel(model=model_name, openai_client=client)

    if provider in ("huggingface", "hf"):
        base_url = os.getenv("HF_ENDPOINTS_BASE_URL")
        model_name = os.getenv("HF_MODEL", "HuggingFaceTB/SmolLM3-3B")
        logger.info(f"Using HuggingFace: model={model_name}")
        client = AsyncOpenAI(api_key=os.getenv("HF_API_KEY", "not-needed"), base_url=f"{base_url}/v1")
        return OpenAIChatCompletionsModel(model=model_name, openai_client=client)

    if provider == "kimi":
        model_name = os.getenv("KIMI_MODEL", "moonshotai/Kimi-K2-Instruct-0905")
        logger.info(f"Using Kimi: model={model_name}")
        client = AsyncOpenAI(api_key=os.getenv("KIMI_API_KEY"), base_url="https://inference.baseten.co/v1")
        return OpenAIChatCompletionsModel(model=model_name, openai_client=client)

    model_name = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    logger.info(f"Using OpenAI: model={model_name}")
    return model_name


credit_card_agent = Agent(
    name="Credit Card Agent",
    instructions=agent_desc,
    model=get_model(),
    tools=[
        display_user_info,
        display_card_info_by_last4,
        change_card_status,
        request_card_replacement,
        update_card_replacement_status,
    ],
)
