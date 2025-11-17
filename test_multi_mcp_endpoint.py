# Databricks notebook source
# MAGIC %md
# MAGIC # Testing Multi-MCP Agent Endpoint
# MAGIC
# MAGIC This notebook demonstrates how to connect to and test the deployed Multi-MCP Agent endpoint.
# MAGIC
# MAGIC **Endpoint Details:**
# MAGIC - Model: `kat_savchyn.ai.kat_multi_mcp` (version 4)
# MAGIC - Endpoint: `agents_kat_savchyn-ai-kat_multi_mcp`
# MAGIC - Profile: `e2-demo`

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup and Configuration

# COMMAND ----------

import requests
import json
from databricks.sdk import WorkspaceClient

# Configuration
ENDPOINT_NAME = "agents_kat_savchyn-ai-kat_multi_mcp"
DATABRICKS_CLI_PROFILE = "e2-demo"

# Initialize workspace client
ws = WorkspaceClient(profile=DATABRICKS_CLI_PROFILE)

print(f"✅ Connected to workspace: {ws.config.host}")
print(f"🎯 Target endpoint: {ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 1: Query Available Tools
# MAGIC
# MAGIC Ask the agent what tools it has available

# COMMAND ----------

def query_endpoint(messages, max_tokens=1000):
    """Query the Multi-MCP Agent endpoint"""

    # Prepare the request payload
    payload = {
        "input": messages,
        "config": {
            "max_tokens": max_tokens
        }
    }

    # Get the endpoint URL
    endpoint_url = f"{ws.config.host}/serving-endpoints/{ENDPOINT_NAME}/invocations"

    # Get authentication headers
    headers = ws.config.authenticate()
    headers["Content-Type"] = "application/json"

    try:
        response = requests.post(
            endpoint_url,
            headers=headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"❌ Error querying endpoint: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
        return None

# Test query for available tools
test_messages = [
    {
        "role": "user",
        "content": "What tools do you have available? Please list all your capabilities and briefly describe what each tool does."
    }
]

print("🔍 Querying endpoint for available tools...")
result = query_endpoint(test_messages)

if result:
    print("✅ Query successful!")
    print("\n📋 Response:")
    print("=" * 60)

    # Extract and display the response
    if 'output' in result:
        for output_item in result['output']:
            if output_item.get('type') == 'message':
                content = output_item.get('content', [])
                for content_item in content:
                    if content_item.get('type') == 'output_text':
                        print(content_item.get('text', ''))
    else:
        print(json.dumps(result, indent=2))

    print("=" * 60)
else:
    print("❌ Failed to query endpoint")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 2: Test Managed Tools (Unity Catalog)
# MAGIC
# MAGIC Test the Python execution capability

# COMMAND ----------

python_test_messages = [
    {
        "role": "user",
        "content": "Please use Python to calculate the first 10 Fibonacci numbers and display them as a list."
    }
]

print("🐍 Testing Python execution via Unity Catalog...")
result = query_endpoint(python_test_messages)

if result:
    print("✅ Python execution test successful!")
    print("\n📊 Response:")
    print("=" * 60)

    if 'output' in result:
        for output_item in result['output']:
            if output_item.get('type') == 'message':
                content = output_item.get('content', [])
                for content_item in content:
                    if content_item.get('type') == 'output_text':
                        print(content_item.get('text', ''))

    print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 3: Test Custom MCP Server Tools
# MAGIC
# MAGIC Test the custom tools from the external MCP server

# COMMAND ----------

custom_tools_test_messages = [
    {
        "role": "user",
        "content": "Please test your connection to the custom MCP server and then echo back 'Hello from custom MCP tools!' using the echo function."
    }
]

print("🔧 Testing custom MCP server tools...")
result = query_endpoint(custom_tools_test_messages)

if result:
    print("✅ Custom tools test successful!")
    print("\n🔧 Response:")
    print("=" * 60)

    if 'output' in result:
        for output_item in result['output']:
            if output_item.get('type') == 'message':
                content = output_item.get('content', [])
                for content_item in content:
                    if content_item.get('type') == 'output_text':
                        print(content_item.get('text', ''))

    print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 4: Multi-Tool Orchestration
# MAGIC
# MAGIC Test the agent's ability to use multiple tools in sequence

# COMMAND ----------

orchestration_test_messages = [
    {
        "role": "user",
        "content": """Please perform the following tasks in sequence:
        1. Test connection to your custom MCP server
        2. Use Python to calculate 25 * 47
        3. Echo back the result using the echo tool
        4. Get user information from the custom server

        Please complete all these tasks and provide a summary of what you accomplished."""
    }
]

print("🎭 Testing multi-tool orchestration...")
result = query_endpoint(orchestration_test_messages, max_tokens=2000)

if result:
    print("✅ Multi-tool orchestration test successful!")
    print("\n🎯 Response:")
    print("=" * 60)

    if 'output' in result:
        for output_item in result['output']:
            if output_item.get('type') == 'message':
                content = output_item.get('content', [])
                for content_item in content:
                    if content_item.get('type') == 'output_text':
                        print(content_item.get('text', ''))

    print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 5: Error Handling
# MAGIC
# MAGIC Test how the agent handles tool errors and edge cases

# COMMAND ----------

error_test_messages = [
    {
        "role": "user",
        "content": "Please try to execute Python code that will intentionally cause an error, like dividing by zero. Show me how you handle errors."
    }
]

print("⚠️ Testing error handling...")
result = query_endpoint(error_test_messages)

if result:
    print("✅ Error handling test completed!")
    print("\n⚠️ Response:")
    print("=" * 60)

    if 'output' in result:
        for output_item in result['output']:
            if output_item.get('type') == 'message':
                content = output_item.get('content', [])
                for content_item in content:
                    if content_item.get('type') == 'output_text':
                        print(content_item.get('text', ''))

    print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC This notebook tested:
# MAGIC
# MAGIC ✅ **Tool Discovery** - Asked the agent about its available capabilities
# MAGIC ✅ **Managed Tools** - Tested Unity Catalog Python execution
# MAGIC ✅ **Custom Tools** - Tested external MCP server tools (test_connection, echo, get_user_info)
# MAGIC ✅ **Multi-Tool Orchestration** - Used multiple tools in sequence
# MAGIC ✅ **Error Handling** - Verified graceful error handling
# MAGIC
# MAGIC ## Expected Available Tools:
# MAGIC
# MAGIC **Managed (Unity Catalog):**
# MAGIC - `system__ai__python_exec` - Execute Python code
# MAGIC
# MAGIC **Custom (External MCP Server):**
# MAGIC - `test_connection` - Test MCP server connectivity
# MAGIC - `echo` - Echo back provided text
# MAGIC - `get_user_info` - Get user information
# MAGIC
# MAGIC ## Next Steps:
# MAGIC - Use this pattern to create more complex multi-tool workflows
# MAGIC - Integrate with your applications using the same endpoint querying approach
# MAGIC - Monitor performance and tool usage through the Databricks ML monitoring

# COMMAND ----------

# MAGIC %md
# MAGIC ## Helper Functions for Production Use

# COMMAND ----------

def create_agent_client(endpoint_name, profile="e2-demo"):
    """Create a reusable client for the Multi-MCP Agent"""

    class MCPAgentClient:
        def __init__(self, endpoint_name, profile):
            self.endpoint_name = endpoint_name
            self.ws = WorkspaceClient(profile=profile)
            self.endpoint_url = f"{self.ws.config.host}/serving-endpoints/{endpoint_name}/invocations"

        def query(self, message, max_tokens=1000):
            """Send a single message to the agent"""
            return self._query_messages([{"role": "user", "content": message}], max_tokens)

        def chat(self, messages, max_tokens=1000):
            """Send a conversation history to the agent"""
            return self._query_messages(messages, max_tokens)

        def _query_messages(self, messages, max_tokens):
            """Internal method to query the endpoint"""
            payload = {
                "input": messages,
                "config": {"max_tokens": max_tokens}
            }

            headers = self.ws.config.authenticate()
            headers["Content-Type"] = "application/json"

            response = requests.post(
                self.endpoint_url,
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            return response.json()

        def extract_text_response(self, result):
            """Extract text from agent response"""
            if 'output' in result:
                text_parts = []
                for output_item in result['output']:
                    if output_item.get('type') == 'message':
                        content = output_item.get('content', [])
                        for content_item in content:
                            if content_item.get('type') == 'output_text':
                                text_parts.append(content_item.get('text', ''))
                return '\n'.join(text_parts)
            return str(result)

    return MCPAgentClient(endpoint_name, profile)

# Example usage of the helper client
print("📚 Example of using the helper client:")
agent = create_agent_client(ENDPOINT_NAME, DATABRICKS_CLI_PROFILE)

# Simple query
try:
    response = agent.query("What's 5 factorial? Use Python to calculate it.")
    text_response = agent.extract_text_response(response)
    print(f"Agent response: {text_response}")
except Exception as e:
    print(f"Error: {e}")

# COMMAND ----------