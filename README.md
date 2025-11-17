# Multi-MCP Agent Endpoint

A Databricks Model Serving endpoint that orchestrates across both managed Databricks tools and custom MCP servers to provide intelligent assistance.

## What it does

This endpoint combines multiple tool sources into a single conversational agent:

**Managed Databricks Tools:**
- `system__ai__python_exec` - Execute Python code using Databricks Unity Catalog

**Custom MCP Server Tools:**
- `test_connection` - Test MCP server connectivity
- `echo` - Echo text for testing
- `get_user_info` - Get user information

The agent can use any combination of these tools to respond to user requests through natural conversation.

## Current Deployment

- **Model:** `kat_savchyn.ai.kat_multi_mcp` (version 4)
- **Endpoint:** `agents_kat_savchyn-ai-kat_multi_mcp`
- **LLM:** Claude 3.5 Sonnet
- **Profile:** e2-demo

## Files

- `mcp_agent.py` - Main agent implementation
- `deploy_mcp_agent.py` - Deployment script
- `external_mcp_client.py` - Client for custom MCP servers
- `test_mcp_server_conn.py` - Connection testing

## Quick Deploy

```bash
source venv_py310/bin/activate
python deploy_mcp_agent.py
```

## Usage

Send requests to the endpoint with natural language that can trigger any combination of the available tools. The agent will automatically orchestrate across managed and custom tools as needed.