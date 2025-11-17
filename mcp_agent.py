import json
import uuid
import asyncio
from typing import Any, Callable, List
from pydantic import BaseModel

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient
from databricks.sdk.credentials_provider import ModelServingUserCredentials
import requests

# 1) EXTERNAL MCP CLIENT (embedded to avoid import issues)
class ExternalMCPTool(BaseModel):
    name: str
    description: str
    inputSchema: dict

class ExternalMCPClient:
    """Simple MCP client for external servers using HTTP JSON-RPC"""

    def __init__(self, server_url: str, workspace_client: WorkspaceClient):
        self.server_url = server_url
        self.workspace_client = workspace_client
        self.headers = workspace_client.config.authenticate()
        self.headers["Content-Type"] = "application/json"

    def list_tools(self) -> List[ExternalMCPTool]:
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
                tools.append(ExternalMCPTool(
                    name=tool_data["name"],
                    description=tool_data["description"],
                    inputSchema=tool_data["inputSchema"]
                ))

            return tools

        except requests.RequestException as e:
            raise Exception(f"Failed to connect to MCP server: {e}")

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
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

def create_external_mcp_tool_function(server_url: str, tool_name: str, ws: WorkspaceClient) -> Callable:
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

# 2) CONFIGURE YOUR ENDPOINTS/PROFILE
LLM_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"
SYSTEM_PROMPT = "You are a helpful assistant. When a users asks to use databricks functions"
DATABRICKS_CLI_PROFILE = "e2-demo"
workspace_client = WorkspaceClient(profile=DATABRICKS_CLI_PROFILE)
host = workspace_client.config.host
# Add more MCP server URLs here if desired, for example:
# f"{host}/api/2.0/mcp/vector-search/prod/billing"
# to include vector search indexes under the prod.billing schema, or
# f"{host}/api/2.0/mcp/genie/<genie_space_id>"
# to include a Genie space
MANAGED_MCP_SERVER_URLS = [
    f"{host}/api/2.0/mcp/functions/system/ai",
]
# Add Custom MCP Servers hosted on Databricks Apps
CUSTOM_MCP_SERVER_URLS = [
    "https://mcp-cust-kat-1444828305810485.aws.databricksapps.com/mcp",
]

# 2) HELPER: convert between ResponsesAgent "message dict" and ChatcCompletions format
def _to_chat_messages(msg: dict[str, Any]) -> List[dict]:
    """
    Take a single ResponsesAgent‐style dict and turn it into one or more
    ChatCompletions‐compatible dict entries.
    """
    msg_type = msg.get("type")
    if msg_type == "function_call":
        return [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": msg["call_id"],
                        "type": "function",
                        "function": {
                            "name": msg["name"],
                            "arguments": msg["arguments"],
                        },
                    }
                ],
            }
        ]
    elif msg_type == "message" and isinstance(msg["content"], list):
        return [
            {
                "role": "assistant" if msg["role"] == "assistant" else msg["role"],
                "content": content["text"],
            }
            for content in msg["content"]
        ]
    elif msg_type == "function_call_output":
        return [
            {
                "role": "tool",
                "content": msg["output"],
                "tool_call_id": msg["tool_call_id"],
            }
        ]
    else:
        # fallback for plain {"role": ..., "content": "..."} or similar
        return [
            {
                k: v
                for k, v in msg.items()
                if k in ("role", "content", "name", "tool_calls", "tool_call_id")
            }
        ]


# 3) "MCP SESSION" + TOOL‐INVOCATION LOGIC
def _make_exec_fn(
    server_url: str, tool_name: str, ws: WorkspaceClient
) -> Callable[..., str]:
    def exec_fn(**kwargs):
        mcp_client = DatabricksMCPClient(server_url=server_url, workspace_client=ws)
        response = mcp_client.call_tool(tool_name, kwargs)
        return "".join([c.text for c in response.content])

    return exec_fn


class ToolInfo(BaseModel):
    name: str
    spec: dict
    exec_fn: Callable


def _fetch_tool_infos(ws: WorkspaceClient, server_url: str, is_external: bool = False) -> List[ToolInfo]:
    print(f"Listing tools from MCP server {server_url} (external={is_external})")
    infos: List[ToolInfo] = []

    if is_external:
        # Use external MCP client for custom servers
        try:
            external_client = ExternalMCPClient(server_url=server_url, workspace_client=ws)
            mcp_tools = external_client.list_tools()
            for t in mcp_tools:
                schema = t.inputSchema.copy()
                if "properties" not in schema:
                    schema["properties"] = {}
                spec = {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": schema,
                    },
                }
                infos.append(
                    ToolInfo(
                        name=t.name,
                        spec=spec,
                        exec_fn=create_external_mcp_tool_function(server_url, t.name, ws)
                    )
                )
        except Exception as e:
            print(f"Failed to connect to external MCP server {server_url}: {e}")
            raise
    else:
        # Use DatabricksMCPClient for managed servers
        mcp_client = DatabricksMCPClient(server_url=server_url, workspace_client=ws)
        mcp_tools = mcp_client.list_tools()
        for t in mcp_tools:
            schema = t.inputSchema.copy()
            if "properties" not in schema:
                schema["properties"] = {}
            spec = {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": schema,
                },
            }
            infos.append(
                ToolInfo(
                    name=t.name, spec=spec, exec_fn=_make_exec_fn(server_url, t.name, ws)
                )
            )
    return infos


# 4) MULTI-TURN AGENT CLASS
class MultiTurnMCPAgent(ResponsesAgent):
    def _call_llm(self, history: List[dict], ws: WorkspaceClient, tool_infos):
        """
        Send current history → LLM, returning the raw response dict.
        """
        client = ws.serving_endpoints.get_open_ai_client()
        flat_msgs = []
        for msg in history:
            flat_msgs.extend(_to_chat_messages(msg))
        return client.chat.completions.create(
            model=LLM_ENDPOINT_NAME,
            messages=flat_msgs,
            tools=[ti.spec for ti in tool_infos],
        )

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        # Try on-behalf-of-user authentication first, fallback to service principal
        tool_infos = []
        ws = None

        # First try OBO authentication
        try:
            print("Attempting on-behalf-of-user authentication...")
            ws = WorkspaceClient(credentials_strategy=ModelServingUserCredentials())

            # Test if we can access at least one MCP server
            test_url = f"{ws.config.host}/api/2.0/mcp/functions/system/ai"
            _fetch_tool_infos(ws, test_url)
            print("✅ OBO authentication successful")

        except Exception as obo_error:
            print(f"❌ OBO authentication failed: {obo_error}")
            print("🔄 Falling back to service principal authentication...")
            try:
                ws = WorkspaceClient(profile=DATABRICKS_CLI_PROFILE)
                print("✅ Service principal authentication successful")
            except Exception as sp_error:
                print(f"❌ Service principal authentication also failed: {sp_error}")
                # Continue with limited functionality
                ws = WorkspaceClient(credentials_strategy=ModelServingUserCredentials())

        # 1) build initial history: system + user
        history: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for inp in request.input:
            history.append(inp.model_dump())

        # 2) call LLM once - initialize tools with detailed error reporting
        print(f"🔍 RUNTIME DEBUG: About to load tools from {len(MANAGED_MCP_SERVER_URLS + CUSTOM_MCP_SERVER_URLS)} servers")
        print(f"🔍 Managed servers: {MANAGED_MCP_SERVER_URLS}")
        print(f"🔍 Custom servers: {CUSTOM_MCP_SERVER_URLS}")
        print(f"🔍 Workspace client host: {ws.config.host}")
        print(f"🔍 Workspace client auth: {ws.config.auth_type}")

        # Load managed MCP servers
        for mcp_server_url in MANAGED_MCP_SERVER_URLS:
            try:
                print(f"🔍 Attempting to connect to managed server: {mcp_server_url}")
                server_tools = _fetch_tool_infos(ws, mcp_server_url, is_external=False)
                tool_infos.extend(server_tools)
                print(f"✅ Successfully loaded {len(server_tools)} managed tools from {mcp_server_url}")
                for tool in server_tools:
                    print(f"   - {tool.name}")
            except Exception as e:
                print(f"❌ Failed to access managed MCP server {mcp_server_url}: {type(e).__name__}: {e}")
                # Continue with other servers

        # Load custom/external MCP servers
        for mcp_server_url in CUSTOM_MCP_SERVER_URLS:
            try:
                print(f"🔍 Attempting to connect to external server: {mcp_server_url}")
                server_tools = _fetch_tool_infos(ws, mcp_server_url, is_external=True)
                tool_infos.extend(server_tools)
                print(f"✅ Successfully loaded {len(server_tools)} external tools from {mcp_server_url}")
                for tool in server_tools:
                    print(f"   - {tool.name}")
            except Exception as e:
                print(f"❌ Failed to access external MCP server {mcp_server_url}: {type(e).__name__}: {e}")
                import traceback
                print(f"🔍 Full error trace: {traceback.format_exc()}")
                # Continue with other servers

        print(f"🔍 RUNTIME DEBUG: Total tools loaded: {len(tool_infos)}")
        tools_dict = {tool_info.name: tool_info for tool_info in tool_infos}

        # Multi-turn conversation loop
        max_turns = 10  # Prevent infinite loops
        turn_count = 0

        while turn_count < max_turns:
            turn_count += 1
            print(f"🔄 Turn {turn_count}: Calling LLM...")

            llm_resp = self._call_llm(history, ws, tool_infos)
            raw_choice = llm_resp.choices[0].message.to_dict()
            raw_choice["id"] = uuid.uuid4().hex
            history.append(raw_choice)

            tool_calls = raw_choice.get("tool_calls") or []
            print(f"🔍 LLM response: content={raw_choice.get('content', 'None')[:100]}...")
            print(f"🔍 Tool calls found: {len(tool_calls)}")
            if tool_calls:
                for i, tc in enumerate(tool_calls):
                    print(f"   Tool {i+1}: {tc.get('function', {}).get('name', 'Unknown')}")

            if not tool_calls:
                # No more tool calls - conversation is complete
                print(f"✅ Conversation completed after {turn_count} turns")
                assistant_text = raw_choice.get("content", "")
                return ResponsesAgentResponse(
                    output=[
                        {
                            "id": uuid.uuid4().hex,
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": assistant_text}],
                        }
                    ],
                    custom_outputs=request.custom_inputs,
                )

            # Process all tool calls in this turn
            print(f"🔧 Processing {len(tool_calls)} tool call(s)...")
            for fc in tool_calls:
                name = fc["function"]["name"]
                args = json.loads(fc["function"]["arguments"])
                print(f"📞 Calling tool: {name}")

                try:
                    tool_info = tools_dict[name]
                    result = tool_info.exec_fn(**args)
                    print(f"✅ Tool {name} succeeded")
                except Exception as e:
                    result = f"Error invoking {name}: {e}"
                    print(f"❌ Tool {name} failed: {e}")

                # Append each tool result to history
                history.append(
                    {
                        "type": "function_call_output",
                        "role": "tool",
                        "id": uuid.uuid4().hex,
                        "tool_call_id": fc["id"],
                        "output": result,
                    }
                )

        # If we hit max_turns, return the last assistant message
        print(f"⚠️ Reached maximum turns ({max_turns}), ending conversation")
        assistant_text = "I've completed the requested tasks but reached the maximum conversation turns."
        return ResponsesAgentResponse(
            output=[
                {
                    "id": uuid.uuid4().hex,
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": assistant_text}],
                }
            ],
            custom_outputs=request.custom_inputs,
        )

    def predict_stream(self, request: ResponsesAgentRequest):
        """
        Streaming version - just calls predict and yields the response
        """
        print("🔍 STREAM: predict_stream called - delegating to predict()")
        response = self.predict(request)
        yield response


mlflow.models.set_model(MultiTurnMCPAgent())

if __name__ == "__main__":
    req = ResponsesAgentRequest(
        input=[{"role": "user", "content": "What's the 100th Fibonacci number?"}]
    )
    resp = MultiTurnMCPAgent().predict(req)
    for item in resp.output:
        print(item)