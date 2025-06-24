"""
This script serves as the main entry point for the FAS LLM Flows
It sets up the necessary import paths and initializes core connections.
"""
import os
import sys

# This ensures that the 'fas_llm_applications' package root is on sys.path
# when the script is run directly from its subdirectory.
script_directory = os.path.dirname(os.path.abspath(__file__)) # This script
fas_root_dir = os.path.abspath(os.path.join(script_directory, '../')) # fas_llm_applications root directory
print("fas_root_dir", fas_root_dir, file=sys.stderr)
flow_root_dir = os.path.abspath(os.path.join(script_directory, '../digital_latin_project/')) # project directory
dotenv_file_path = os.path.join(flow_root_dir, '.env')

sys.path.insert(0, '/Users/kevingray/codebase/harvard-atg/promptflow')

from dotenv import load_dotenv

print("Current sys.path:", sys.path, file=sys.stderr)
from fas_llm_applications._connections_manager_.aws_connection_utils import ensure_promptflow_aws_connection
from fas_llm_applications._connections_manager_.gemini_connection_utils import ensure_promptflow_gemini_connection
from fas_llm_applications._connections_manager_.common_secrets_loader import get_env_var
from fas_llm_applications._connections_manager_.keyring_utils import verify_keyring
from fas_llm_applications._connections_manager_.client_utils import get_pf_client

AWS_CONNECTION_NAME = "bedrock_connection"
GEMINI_CONNECTION_NAME = "gemini_connection"
BEDROCK_SERVICE_NAME = "bedrock-runtime"

load_dotenv(dotenv_path=dotenv_file_path, override=True)

def setup_all_connections():
    print("\n--- Ensuring Connections ---")

    # This is to setup Keyring in linux as a place to hold sensitive parameters of connection objects created below.
    verify_keyring()

    # Get the pf client singleton
    promptflow_client = get_pf_client()

    # Ensure AWS Connection
    try:
        # Get env vars using secrets load utility after dotenv is loaded
        aws_access_key = get_env_var("AWS_AI_WORKFLOW_CORE_DEV_ID")
        aws_secret_key = get_env_var("AWS_AI_WORKFLOW_CORE_DEV_SECRET")
        aws_region = get_env_var("AWS_DEFAULT_REGION") or "us-east-1"
        ensure_promptflow_aws_connection(
            access_key=aws_access_key,
            secret_key=aws_secret_key,
            region=aws_region,
            pf_client=promptflow_client,
            connection_name=AWS_CONNECTION_NAME
        )
        print("Successful Connection: AWS Bedrock")
    except Exception as e:
        print(f"Failed to setup AWS Bedrock Connection: {e}")

    # Ensure Gemini Connection
    try:
        gemini_api_key = get_env_var("GEMINI_API_KEY")
        gemini_base_url = get_env_var("GEMINI_BASE_URL")

        if not all([gemini_api_key, gemini_base_url]):
            raise ValueError(f"Missing required environment variables for Gemini connection. API Key: {gemini_api_key}, Base URL: {gemini_base_url}")

        ensure_promptflow_gemini_connection(
            api_key=gemini_api_key,
            base_url=gemini_base_url,
            pf_client=promptflow_client,
            connection_name=GEMINI_CONNECTION_NAME
        )
        print("Successful Connection: Google Gemini")
    except Exception as e:
        print(f"Failed to setup Gemini Connection: {e}")

    print("--- All Connections Successful ---")

if __name__ == "__main__":
    setup_all_connections()
