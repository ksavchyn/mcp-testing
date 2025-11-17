# Custom MCP Server for Databricks

Custom Model Context Protocol (MCP) server with OBO (On-Behalf-Of) authentication, designed for deployment as a Databricks app.

## Features

The server implements three MCP tools:

- **test_connection**: Test server connectivity and OBO authentication status
- **echo**: Echo back a message (useful for testing basic functionality)
- **get_user_info**: Retrieve current user information via OBO authentication

## Authentication

This server uses Databricks OBO (On-Behalf-Of) authentication with `ModelServingUserCredentials`, allowing it to act on behalf of the authenticated user making requests.

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
   databricks apps create mcp-cust-kat
   ```

2. Upload and deploy:
   ```bash
   DATABRICKS_USERNAME=$(databricks current-user me | jq -r .userName)
   databricks sync . "/Users/$DATABRICKS_USERNAME/mcp-cust-kat"
   databricks apps deploy mcp-cust-kat --source-code-path "/Workspace/Users/$DATABRICKS_USERNAME/mcp-cust-kat"
   ```

3. Access your app:
   - The app URL will be available in the Databricks UI
   - MCP endpoint: `https://<app-url>/mcp`
   - Health check: `https://<app-url>/health`

## API Endpoints

- **GET /** - Root endpoint with server information
- **GET /health** - Health check endpoint with OBO authentication status
- **POST /mcp** - Main MCP JSON-RPC endpoint

## Testing the Server

Once deployed, you can test the connection using the available MCP tools:

1. **test_connection**: Verifies the server is running and shows OBO authentication status
2. **echo**: Simple echo test to verify request/response functionality
3. **get_user_info**: Returns detailed information about the authenticated user

## Local Development

Run locally for testing:
```bash
uv run python server.py
```

The server will start on port 8000 with both HTTP and MCP protocol support.

## Project Structure

- `server.py` - Main FastAPI application with MCP protocol implementation
- `app.yaml` - Databricks app configuration
- `pyproject.toml` - Python project configuration and dependencies
- `requirements.txt` - Direct dependencies for the application