"""
Simple MCP client for external MCP servers that use HTTP JSON-RPC transport.
This works alongside DatabricksMCPClient for managed Databricks MCP servers.
"""

import requests
import json
from typing import List, Dict, Any, Callable
from pydantic import BaseModel
from databricks.sdk import WorkspaceClient


class MCPTool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]


class ExternalMCPClient:
    """Simple MCP client for external servers using HTTP JSON-RPC"""

    def __init__(self, server_url: str, workspace_client: WorkspaceClient):
        self.server_url = server_url
        self.workspace_client = workspace_client
        self.headers = workspace_client.config.authenticate()
        self.headers["Content-Type"] = "application/json"

    def list_tools(self) -> List[MCPTool]:
        """List tools available on the MCP server"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }

        try:
            response = requests.post(
                self.server_url,
                headers=self.headers,
                json=request,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            if "error" in result:
                raise Exception(f"MCP error: {result['error']}")

            tools = []
            for tool_data in result["result"]["tools"]:
                tools.append(MCPTool(
                    name=tool_data["name"],
                    description=tool_data["description"],
                    inputSchema=tool_data["inputSchema"]
                ))

            return tools

        except requests.RequestException as e:
            raise Exception(f"Failed to connect to MCP server: {e}")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server"""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        try:
            response = requests.post(
                self.server_url,
                headers=self.headers,
                json=request,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            if "error" in result:
                raise Exception(f"MCP error: {result['error']}")

            return result["result"]

        except requests.RequestException as e:
            raise Exception(f"Failed to call MCP tool: {e}")


def create_mcp_tool_function(server_url: str, tool_name: str, ws: WorkspaceClient) -> Callable:
    """Create a function that can call an external MCP tool"""
    def tool_function(**kwargs):
        client = ExternalMCPClient(server_url, ws)
        result = client.call_tool(tool_name, kwargs)

        # Extract text content from MCP response
        if isinstance(result, dict) and "content" in result:
            if isinstance(result["content"], list):
                return "".join([item.get("text", str(item)) for item in result["content"]])
            else:
                return str(result["content"])
        else:
            return str(result)

    return tool_function