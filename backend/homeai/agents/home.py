"""Optional conversational LangGraph agent, using only read-only MCP tools.

MCPAdapter from LangChain 1.4+ remains beta. If any MCP server is unavailable,
return a clearly marked service error; don't fabricate device facts.
"""
import os
from ..config import get_settings

SYSTEM_PROMPT = """You are a private home energy and security assistant.
Only answer real-time household data questions using provided MCP tools.
Never invent telemetry, tariff values, security events or successful device changes.
Explain that forecasts are uncertain and the energy plan is simulation-only.
All tools are read-only. Never request credentials or secrets in chat.
For security, do not identify people or infer sensitive personal attributes from images.
"""


async def answer(message: str) -> str:
    cfg = get_settings()
    if not cfg.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured; chat is optional, energy planning still works")
    from langchain.mcp import MCPAdapter
    from langchain.agents import create_agent

    # LangChain MCPAdapter accepts a mapping of server names to connection settings.
    # MCP tools are intentionally read-only. No executor tools are advertised.
    servers = {
        "foxess": {"url": cfg.mcp_foxess_url},
        "octopus": {"url": cfg.mcp_octopus_url},
        "unifi": {"url": cfg.mcp_unifi_url},
        "optimiser": {"url": cfg.mcp_optimiser_url},
    }
    async with MCPAdapter(servers) as adapter:
        tools = await adapter.list_tools()
        agent = create_agent(model=f"openai:{cfg.openai_model}", tools=tools, system_prompt=SYSTEM_PROMPT)
        result = await agent.ainvoke({"messages": [{"role": "user", "content": message}]})
        last = result["messages"][-1]
        return str(last.content)
