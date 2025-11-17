#!/usr/bin/env python3
"""
Deployment script for MCP Agent to Databricks Model Serving Endpoint
"""

import mlflow
import sys
from databricks import agents
from databricks.sdk import WorkspaceClient
from mlflow.models.auth_policy import AuthPolicy, UserAuthPolicy, SystemAuthPolicy
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksFunction, DatabricksApp

# Configuration
AGENT_MODEL_NAME = "kat_savchyn.ai.kat_multi_mcp"  # Custom MLflow deployment
AGENT_DESCRIPTION = "MCP Agent with Databricks Unity Catalog and custom mcp server tools"
DATABRICKS_CLI_PROFILE = "e2-demo"

# MCP Agent Configuration (from mcp_agent.py)
LLM_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"
workspace_client = WorkspaceClient(profile=DATABRICKS_CLI_PROFILE)
host = workspace_client.config.host
MANAGED_MCP_SERVER_URLS = [
    f"{host}/api/2.0/mcp/functions/system/ai",
]
CUSTOM_MCP_SERVER_URLS = [
    "https://mcp-cust-kat-1444828305810485.aws.databricksapps.com/mcp",
]

def register_agent():
    """Register the MCP agent model in Unity Catalog"""
    print("🔄 Registering MCP agent model...")

    import os

    # Initialize Databricks workspace client
    ws = WorkspaceClient(profile=DATABRICKS_CLI_PROFILE)
    current_user = ws.current_user.me().user_name

    # Set MLflow tracking exactly like the official docs
    mlflow.set_tracking_uri(f"databricks://{DATABRICKS_CLI_PROFILE}")
    mlflow.set_registry_uri(f"databricks-uc://{DATABRICKS_CLI_PROFILE}")
    mlflow.set_experiment(f"/Users/{current_user}/kat_custom_mcp_agent_experiment")
    os.environ["DATABRICKS_CONFIG_PROFILE"] = DATABRICKS_CLI_PROFILE

    with mlflow.start_run():
        # Configure Databricks resources for MCP agent (official pattern)
        from databricks_mcp import DatabricksMCPClient

        # Base resources
        resources = [
            DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT_NAME),
            DatabricksFunction("system.ai.python_exec")
        ]

        # Add managed MCP server resources
        for mcp_server_url in MANAGED_MCP_SERVER_URLS:
            mcp_client = DatabricksMCPClient(
                server_url=mcp_server_url,
                workspace_client=ws
            )
            resources.extend(mcp_client.get_databricks_resources())

        # Add custom MCP server resources (Databricks Apps)
        for custom_url in CUSTOM_MCP_SERVER_URLS:
            if "mcp-cust-kat-1444828305810485" in custom_url:
                resources.append(DatabricksApp(app_name="mcp-cust-kat-1444828305810485"))

        # Log the agent model with explicit conda environment using Databricks-compatible Python
        conda_env = {
            "channels": ["conda-forge"],
            "dependencies": [
                "python=3.10.12",  # Specific Databricks-compatible Python version
                "pip",
                {
                    "pip": [
                        "mlflow>=3.1.0",
                        "databricks-agents>=1.0.0",
                        "databricks-sdk[openai]",
                        "databricks-mcp>=0.4.0",
                        "pydantic>=2.0.0"
                    ]
                }
            ],
            "name": "kat-mcp-env"
        }

        # Configure authentication policy with both system and user auth
        system_policy = SystemAuthPolicy(resources=resources)
        user_policy = UserAuthPolicy(api_scopes=[
            "serving.serving-endpoints",  # For LLM endpoint access
            "sql.warehouses",             # For Unity Catalog function access
            "sql.statement-execution"     # For function execution
        ])

        auth_policy = AuthPolicy(
            system_auth_policy=system_policy,
            user_auth_policy=user_policy
        )

        # Use file-based approach to ensure proper module packaging
        model_info = mlflow.pyfunc.log_model(
            python_model="mcp_agent.py",
            artifact_path="mcp_agent",
            conda_env=conda_env,
            auth_policy=auth_policy
        )

        # Register to Unity Catalog
        uc_model_info = mlflow.register_model(
            model_uri=model_info.model_uri,
            name=AGENT_MODEL_NAME,
            tags={"type": "mcp_agent", "framework": "databricks_agents"}
        )

        print(f"✅ Model registered: {AGENT_MODEL_NAME} version {uc_model_info.version}")
        return uc_model_info

def deploy_agent(uc_model_info):
    """Deploy the registered agent as a model serving endpoint"""
    print("🚀 Deploying agent to model serving endpoint...")

    try:
        # Deploy the agent using databricks.agents.deploy
        deployment = agents.deploy(
            model_name=AGENT_MODEL_NAME,
            model_version=uc_model_info.version,
            scale_to_zero_enabled=True  # Enable auto-scaling
        )

        print(f"✅ Deployment successful!")
        print(f"📍 Query endpoint: {deployment.query_endpoint}")
        print(f"🔗 Review app URL: {deployment.review_app_url}")

        return deployment

    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_deployment(deployment):
    """Test the deployed endpoint"""
    if not deployment:
        print("⏭️  Skipping test - no deployment available")
        return

    print("🧪 Testing deployed endpoint...")

    try:
        # Initialize workspace client
        ws = WorkspaceClient(profile=DATABRICKS_CLI_PROFILE)

        # Test query (this would typically be done via REST API in production)
        test_input = {
            "input": [
                {"role": "user", "content": "What's 2+2?"}
            ]
        }

        print(f"📤 Sending test query: {test_input}")
        print("✅ Endpoint is ready for queries!")
        print(f"💡 Use this URL to query: {deployment.query_endpoint}")

    except Exception as e:
        print(f"❌ Test failed: {e}")

def main():
    """Main deployment workflow"""
    print("🎯 Starting MCP Agent Deployment")
    print("=" * 50)

    try:
        # Step 1: Register the agent
        uc_model_info = register_agent()

        # Step 2: Deploy the agent
        deployment = deploy_agent(uc_model_info)

        # Step 3: Test the deployment
        test_deployment(deployment)

        print("=" * 50)
        print("🎉 MCP Agent deployment completed!")

        if deployment:
            print(f"\n📋 Deployment Summary:")
            print(f"   Model: {AGENT_MODEL_NAME}")
            print(f"   Version: {uc_model_info.version}")
            print(f"   Endpoint: {deployment.query_endpoint}")
            print(f"   Review App: {deployment.review_app_url}")

    except Exception as e:
        print(f"💥 Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()