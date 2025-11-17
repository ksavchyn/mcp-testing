#!/usr/bin/env python3
"""
Custom MCP server with OBO authentication following Databricks documentation.
Uses ModelServingUserCredentials for proper OBO authentication.
"""
import os
import logging
import json
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from databricks.sdk import WorkspaceClient
from databricks.sdk.credentials_provider import ModelServingUserCredentials
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="MCP Custom Server with OBO",
    version="1.0.0",
    description="Model Context Protocol server with Databricks OBO authentication"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_workspace_client(request: Request = None):
    """Get WorkspaceClient with OBO authentication using incoming Bearer token."""
    try:
        # Check for Bearer token in the request headers
        if request:
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
                # Create WorkspaceClient using the incoming Bearer token
                w = WorkspaceClient(
                    host=os.getenv("DATABRICKS_HOST"),
                    token=token
                )
                return w

        # Fallback: Use ModelServingUserCredentials for OBO as recommended in docs
        if os.getenv("DATABRICKS_HOST"):
            # In Databricks Apps environment, use OBO credentials
            credentials = ModelServingUserCredentials()
            w = WorkspaceClient(credentials_provider=credentials)
            return w
        else:
            # Fallback to default client for local testing
            return WorkspaceClient()
    except Exception as e:
        logger.warning(f"Failed to create WorkspaceClient with OBO: {e}")
        try:
            # Fallback to default WorkspaceClient
            return WorkspaceClient()
        except Exception as e2:
            logger.error(f"Failed to create any WorkspaceClient: {e2}")
            return None

def get_current_user_via_obo(request: Request = None):
    """Get current user information using OBO authentication."""
    try:
        w = get_workspace_client(request)
        if not w:
            return None

        current_user = w.current_user.me()
        return {
            "id": current_user.id,
            "user_name": current_user.user_name,
            "display_name": current_user.display_name,
            "active": current_user.active,
            "emails": [email.value for email in (current_user.emails or [])],
            "groups": [group.display for group in (current_user.groups or [])]
        }
    except Exception as e:
        logger.warning(f"OBO authentication failed: {e}")
        return None

# MCP Protocol Implementation
@app.post("/mcp")
async def handle_mcp_request(request: Request):
    """Handle MCP JSON-RPC requests at the standard /mcp endpoint."""
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        logger.info(f"MCP request: {method}")
        logger.info(f"Request headers: {dict(request.headers)}")

        # Handle initialize
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "mcp-custom-server",
                        "version": "1.0.0"
                    }
                }
            }
            return JSONResponse(response)

        # Handle tools/list
        elif method == "tools/list":
            tools = [
                {
                    "name": "test_connection",
                    "description": "Test the connection and OBO authentication",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "echo",
                    "description": "Echo back a message",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "Message to echo back"
                            }
                        },
                        "required": ["message"]
                    }
                },
                {
                    "name": "get_user_info",
                    "description": "Get current user information via OBO authentication",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            ]

            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": tools
                }
            }
            return JSONResponse(response)

        # Handle tools/call
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name == "test_connection":
                user_info = get_current_user_via_obo(request)
                if user_info:
                    content = f"✅ OBO Authentication successful! Connected as: {user_info.get('user_name', 'Unknown')}"
                else:
                    content = "⚠️  OBO Authentication not available in this environment"

                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": content
                            }
                        ]
                    }
                }
                return JSONResponse(response)

            elif tool_name == "echo":
                message = arguments.get("message", "No message provided")
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Echo: {message}"
                            }
                        ]
                    }
                }
                return JSONResponse(response)

            elif tool_name == "get_user_info":
                user_info = get_current_user_via_obo(request)
                if user_info:
                    content = f"Current user information:\n{json.dumps(user_info, indent=2)}"
                else:
                    content = "Unable to retrieve user information. OBO authentication may not be available."

                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": content
                            }
                        ]
                    }
                }
                return JSONResponse(response)

            else:
                # Unknown tool
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }
                return JSONResponse(response, status_code=400)

        else:
            # Unknown method
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            return JSONResponse(response, status_code=400)

    except Exception as e:
        logger.error(f"Error handling MCP request: {e}")
        response = {
            "jsonrpc": "2.0",
            "id": body.get("id") if "body" in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }
        return JSONResponse(response, status_code=500)

# Health check endpoint
@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint"""
    user_info = get_current_user_via_obo(request)
    return {
        "status": "healthy",
        "server": "mcp-custom-server",
        "version": "1.0.0",
        "obo_available": user_info is not None,
        "user": user_info.get("user_name") if user_info else "Not authenticated"
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with server information"""
    return {
        "name": "MCP Custom Server",
        "version": "1.0.0",
        "protocol": "Model Context Protocol",
        "endpoints": {
            "mcp": "/mcp",
            "health": "/health"
        }
    }

def main():
    """Main entry point for the server as specified in pyproject.toml"""
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting MCP server on port {port}")

    # Check OBO availability at startup
    user_info = get_current_user_via_obo()
    if user_info:
        logger.info(f"OBO authentication available for user: {user_info.get('user_name')}")
    else:
        logger.info("OBO authentication not available (this is normal for local testing)")

    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()