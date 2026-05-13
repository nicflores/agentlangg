from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from agent.config import settings

SYSTEM_PROMPT = (
    "You are a data assistant with access to a customer/orders database via MCP "
    "tools. Prefer the curated tools (get_customer, get_customer_orders, "
    "get_customer_summary). Use run_sql only when no curated tool fits, and "
    "always supply a one-sentence justification. Respond in plain text."
)


def _build_mcp_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "postgres-data": {
                "transport": "streamable_http",
                "url": settings.mcp_server_url,
            }
        }
    )


def _build_model() -> ChatOllama:
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=settings.ollama_temperature,
    )


async def build_agent():
    """Assemble the LangGraph ReAct agent.

    Discovers tools from the MCP server at runtime — adding a new tool on the
    server side requires no code change here. Restart the agent and it picks
    up the new schema on the next ``get_tools()`` call.
    """
    mcp_client = _build_mcp_client()
    tools = await mcp_client.get_tools()

    model = _build_model()

    return create_react_agent(model, tools, prompt=SYSTEM_PROMPT)
