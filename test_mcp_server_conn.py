from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient

# Updated to use the e2-demo profile which points to our workspace
databricks_cli_profile = "e2-demo"
workspace_client = WorkspaceClient(profile=databricks_cli_profile)
workspace_hostname = workspace_client.config.host
mcp_server_url = f"{workspace_hostname}/api/2.0/mcp/functions/system/ai"

# This code uses the Unity Catalog functions MCP server to expose built-in
# AI tools under `system.ai`, like the `system.ai.python_exec` code interpreter tool
def test_connect_to_server():
    mcp_client = DatabricksMCPClient(server_url=mcp_server_url, workspace_client=workspace_client)
    tools = mcp_client.list_tools()

    print(
        f"Discovered tools {[t.name for t in tools]} "
        f"from MCP server {mcp_server_url}"
    )

    result = mcp_client.call_tool(
        "system__ai__python_exec", {"code": "print('Hello, world!')"}
    )
    print(
        f"Called system__ai__python_exec tool and got result "
        f"{result.content}"
    )


if __name__ == "__main__":
    test_connect_to_server()