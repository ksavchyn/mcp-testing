b# Custom MCP Server for Databricks by Kat

Custom Model Context Protocol (MCP) server designed for deployment as a Databricks app.

## Features

- **test_connection**: Test server connectivity and responsiveness
- **get_server_info**: Get server status and capabilities
- **store_message**: Store messages for testing persistence
- **get_stored_messages**: Retrieve stored messages

## Deployment to Databricks

### Prerequisites

1. Install Databricks CLI
2. Authenticate to your workspace:
   ```bash
   databricks auth login --host https://<your-workspace-hostname>
   ```

### Deploy Steps

1. Create the Databricks app:
   ```bash
   databricks apps create mcp-custom-server-kat
   ```

2. Upload and deploy:
   ```bash
   DATABRICKS_USERNAME=$(databricks current-user me | jq -r .userName)
   databricks sync . "/Users/$DATABRICKS_USERNAME/mcp-custom-server-kat"
   databricks apps deploy mcp-custom-server-kat --source-code-path "/Workspace/Users/$DATABRICKS_USERNAME/mcp-custom-server-kat"
   ```

3. Access your app:
   - The app URL will be available in the Databricks UI
   - MCP endpoint: `https://<app-url>/mcp`
   - Health check: `https://<app-url>/health`

## Testing the Server

Once deployed, you can test the connection using the available tools:

1. **test_connection**: Verifies the server is running and responsive
2. **get_server_info**: Returns server metadata and statistics
3. **store_message** / **get_stored_messages**: Test data persistence

## Local Development

Run locally for testing:
```bash
uv run python server.py
```

The server will start on port 8000 with both HTTP and MCP protocol support.