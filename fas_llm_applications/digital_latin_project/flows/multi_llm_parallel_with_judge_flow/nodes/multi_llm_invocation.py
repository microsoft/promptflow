import json
import sys
import os
import time
import boto3
import requests
from promptflow.client import PFClient
from promptflow.core import tool
from promptflow.connections import CustomConnection
from fas_llm_applications._connections_manager_.aws_connection_utils import (
    ensure_promptflow_aws_connection,
)
from fas_llm_applications._connections_manager_.gemini_connection_utils import (
    ensure_promptflow_gemini_connection,
)
from fas_llm_applications._connections_manager_.common_secrets_loader import get_env_var
from fas_llm_applications._connections_manager_.client_utils import get_pf_client
from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
)
from botocore.exceptions import ClientError

PROJECT_ROOT_FOR_TEMPLATES = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../../")
)

CLAUDE_3_7_SONNET_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
DEEPSEEK_MODEL_ID = "us.deepseek.r1-v1:0"
GEMINI_MODEL_ID = "gemini-2.5-pro-preview-05-06"
CLAUDE_4_0_SONNET_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
CLAUDE_4_0_OPUS_MODEL_ID = "us.anthropic.claude-opus-4-20250514-v1:0"
GEMINI_CONNECTION = "gemini_connection"
BEDROCK_CONNECTION = "bedrock_connection"
BEDROCK_SERVICE_NAME = "bedrock-runtime"
GEMINI_BASE_URL = "https://go.apis.huit.harvard.edu/ais-google-gemini"
DEFAULT_REGION = "us-east-1"


@tool
def invoke_llm(
    user_prompt_template_path: str,
    system_prompt_template_path: str,
    system_prompt_id: str,
    user_prompt_id: str,
    model_id: str,
    selector_template_variables: dict = {},
    dynamic_template_variables: dict = {},
) -> dict:
    """
    Invokes the Google Gemini model via the HUIT AI Services API Gateway.
    It renders Jinja templates for prompts before invoking the LLM.

    Args:
        user_prompt_template_path (str): Relative path to the Jinja template file for the user prompt.
        system_prompt_template_path (str): Relative path to the Jinja template file for the system prompt.
        template_variables (dict): A dictionary of variables to pass to the Jinja templates for rendering.
        prompt_id (str): A unique identifier for the specific prompt definition/iteration.
        model_id (str): The specific Gemini model ID (e.g., "gemini-2.0-flash").
        selector_template_variables (dict): Variables from prompt_selector_node
        dynamic_template_variables (dict): Variables from flow inputs (overrides)

    Returns:
        dict: A dictionary containing the LLM's response and other metadata.
              Includes the *rendered* prompts used for reporting, and the prompt_id.
    """
    print(f"Rendering prompts from templates in {PROJECT_ROOT_FOR_TEMPLATES}")

    # Merge template variables within the Python tool
    merged_template_variables = {
        **selector_template_variables,
        **dynamic_template_variables,
    }

    # Set up Jinja2 environment to load templates from the project root
    env = Environment(
        loader=FileSystemLoader(PROJECT_ROOT_FOR_TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
    )

    rendered_user_prompt = ""
    rendered_system_prompt = ""

    # Basic input validation for paths
    if not user_prompt_template_path or not system_prompt_template_path:
        error_msg = "User or System prompt template path cannot be empty."
        return {"error": error_msg, "status": "failed"}

    try:
        # Render System Prompt Template
        system_template = env.get_template(system_prompt_template_path)
        rendered_system_prompt = system_template.render(merged_template_variables)

        # Render User Prompt Template
        user_template = env.get_template(user_prompt_template_path)
        rendered_user_prompt = user_template.render(merged_template_variables)

    except Exception as e:
        return {"error": f"Failed to render Jinja template(s): {e}", "status": "failed"}

    try:
        # Attempt to get connections from the Promptflow Client
        pf_client = get_promptflow_client()
        all_connections = pf_client.connections.list()
        if all_connections:
            connections_list = []
            has_existing_connection = True
            for connection in all_connections:
                connections_list.append(connection.name)
            print(f"Connections found on PF Client - {connections_list}")
        else:
            has_existing_connection = False
            print("No connections found on PF Client")
    except Exception as e:
        print(
            "Error: An error occured when checking Promptflow Client for connections: {e}"
        )
        print("Will build connections instead")
        pass

    if "gemini" in model_id.lower():

        try:
            # Get gemini connection from PF Client
            if (
                GEMINI_CONNECTION in connections_list
                and pf_client.connections.get(name=GEMINI_CONNECTION).configs.get(
                    "base_url"
                )
                == GEMINI_BASE_URL
            ):
                gemini_connection = pf_client.connections.get(name=GEMINI_CONNECTION)

            else:
                # Create new gemini connection
                gemini_connection = create_gemini_connection()

            api_key = gemini_connection.secrets.get("api_key")
            base_url = gemini_connection.configs.get(
                "base_url", "https://go.apis.huit.harvard.edu/ais-google-gemini"
            )

            if not api_key:
                raise ValueError("API key not found in the Gemini connection.")
            if not base_url:
                raise ValueError("Base URL not found in the Gemini connection.")

            api_endpoint = f"{base_url}/v1beta/models/{model_id}:generateContent"

            payload = {
                "contents": [  # Only user messages (and interleaved model messages) go here
                    {"role": "user", "parts": [{"text": rendered_user_prompt}]}
                ]
                # "generationConfig": { # Temporarily remove so we get default model content and behavior
                #     "temperature": temperature,
                #     "maxOutputTokens": max_tokens
                # }
            }

            if rendered_system_prompt:
                payload["system_instruction"] = {
                    "parts": [{"text": rendered_system_prompt}]
                }

            headers = {"Content-Type": "application/json", "api-key": api_key}

            start_time = time.time()
            response = requests.post(api_endpoint, headers=headers, json=payload)
            response.raise_for_status()

            response_json = response.json()
            full_api_response = response_json

            llm_text_response = ""
            if response_json and response_json.get("candidates"):
                for candidate in response_json["candidates"]:
                    if candidate.get("content") and candidate["content"].get("parts"):
                        for part in candidate["content"]["parts"]:
                            if part.get("text"):
                                llm_text_response += part["text"]
            end_time = time.time()
            duration = end_time - start_time

            # The ouput for the Gemini LLM Call
            llm_node_invocation_output = {
                "system_prompt_id": system_prompt_id,
                "user_prompt_id": user_prompt_id,
                "model_id_used": model_id,
                "user_prompt_used": rendered_user_prompt,
                "system_prompt_used": rendered_system_prompt,
                "response_text": llm_text_response,
                "full_api_response": full_api_response,
                "llm_run_time": duration,
                "status": "success",
            }
            return llm_node_invocation_output

        except requests.exceptions.RequestException as e:
            return {"error": f"HTTP Request failed: {e}", "status": "failed"}
        except ValueError as e:
            return {"error": f"Configuration error: {e}", "status": "failed"}
        except Exception as e:
            return {"error": f"An unexpected error occurred: {e}", "status": "failed"}

    else:
        try:
            # Get bedrock connection from PF Client
            if (
                BEDROCK_CONNECTION in connections_list
                and pf_client.connections.get(name=BEDROCK_CONNECTION).configs.get(
                    "region_name"
                )
                == DEFAULT_REGION
            ):
                bedrock_connection = pf_client.connections.get(name=BEDROCK_CONNECTION)

            else:
                # Create new bedrock connection
                bedrock_connection = create_gemini_connection()

            # Retrieve AWS credentials and region from the PromptFlow CustomConnection
            aws_access_key_id = bedrock_connection.secrets.get("aws_access_key_id")
            aws_secret_access_key = bedrock_connection.secrets.get(
                "aws_secret_access_key"
            )
            aws_region = bedrock_connection.configs.get(
                "region_name", "us-east-1"
            )  # Default to us-east-1 if not specified

            if not aws_access_key_id or not aws_secret_access_key:
                raise ValueError(
                    "AWS access_key_id or secret_access_key not found in the Bedrock connection."
                )

            # Initialize Bedrock Runtime client
            bedrock_runtime = boto3.client(
                service_name="bedrock-runtime",
                region_name=aws_region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )

            # Prepare the request body based on the model_id
            body = {}
            llm_text_response = ""
            full_api_response = {}

            if "claude" in model_id.lower() and model_id.lower() in [
                CLAUDE_3_7_SONNET_MODEL_ID,
                CLAUDE_4_0_OPUS_MODEL_ID,
                CLAUDE_4_0_SONNET_MODEL_ID,
            ]:
                # Claude models (e.g., anthropic.claude-3-sonnet-20240229-v1:0)
                print(f"The claude model is {model_id}", file=sys.stderr)
                messages = []
                messages.append({"role": "user", "content": rendered_user_prompt})

                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "system": rendered_system_prompt,
                    "max_tokens": 5000,  # Adjust as needed - Temporarily removed for defualt model response. Initially used 64000, for Claude 4 set to 5000
                    "messages": messages,
                }

                if rendered_system_prompt:
                    body["system"] = rendered_system_prompt

            elif "deepseek" in model_id.lower():
                # Deepseek models (e.g., deepseek-llm-v2)
                messages = []
                if rendered_system_prompt:
                    messages.append(
                        {"role": "system", "content": rendered_system_prompt}
                    )
                messages.append({"role": "user", "content": rendered_user_prompt})

                body = {
                    "messages": messages,
                    "stream": False,
                    "max_tokens": 32000,
                    # "max_tokens": 4000, # Adjust as needed - Temporarily removed for default model reponse
                    # "temperature": 0.7, # Adjust as needed - Temporarily removed for default model response.
                    # "top_p": 1.0, # Adjust as needed - Removed to use default model response
                    # "stop": [] # Adjust as needed - Removed to use default model response
                }
                # Deepseek's response format is similar to OpenAI chat completions

            else:
                raise ValueError(
                    f"Unsupported model_id for Bedrock: {model_id}. Please ensure it's a support Claude or Deepseek model in this flow",
                    file=sys.stderr,
                )

            print(
                f"Invoking Bedrock model: {model_id} in region {aws_region}",
                file=sys.stderr,
            )

            start_time = time.time()
            response = bedrock_runtime.invoke_model(
                body=json.dumps(body),
                modelId=model_id,
                accept="application/json",
                contentType="application/json",
            )
            full_api_response = json.loads(response["body"].read())

            # Parse response based on model type
            if "claude" in model_id.lower():
                if full_api_response.get("content"):
                    for content_block in full_api_response["content"]:
                        if content_block.get("type") == "text":
                            llm_text_response += content_block["text"]

            elif "deepseek" in model_id.lower():
                if full_api_response.get("choices") and full_api_response["choices"][
                    0
                ].get("message"):
                    llm_text_response = full_api_response["choices"][0]["message"].get(
                        "content", ""
                    )
            end_time = time.time()
            duration = end_time - start_time  # Duration in seconds

            llm_node_invocation_output = {
                "system_prompt_id": system_prompt_id,
                "user_prompt_id": user_prompt_id,
                "model_id_used": model_id,
                "response_text": llm_text_response,
                "full_api_response": full_api_response,
                "user_prompt_used": rendered_user_prompt,  # Return the RENDERED user prompt
                "system_prompt_used": rendered_system_prompt,  # Return the RENDERED system prompt
                "llm_run_time": duration,
                "status": "success",
            }
            return llm_node_invocation_output

        except ClientError as e:
            return {
                "error": f"Bedrock Client Error: {e.response['Error']['Message']}",
                "status": "failed",
            }
        except ValueError as e:
            return {"error": f"Configuration or Payload Error: {e}", "status": "failed"}
        except Exception as e:
            return {"error": f"An unexpected error occurred: {e}", "status": "failed"}


def create_aws_connection() -> CustomConnection:

    aws_access_key = get_env_var("AWS_AI_WORKFLOW_CORE_DEV_ID")
    aws_secret_key = get_env_var("AWS_AI_WORKFLOW_CORE_DEV_SECRET")
    aws_region = get_env_var("AWS_DEFAULT_REGION") or "us-east-1"

    connection = ensure_promptflow_aws_connection(
        access_key=aws_access_key,
        secret_key=aws_secret_key,
        region=aws_region,
        connection_name=BEDROCK_CONNECTION,
        service_name=BEDROCK_SERVICE_NAME,
    )
    return connection


def create_gemini_connection() -> CustomConnection:

    api_key = get_env_var("GEMINI_API_KEY")
    base_url = get_env_var("GEMINI_BASE_URL")

    # Create the connection object with desired properties
    connection = CustomConnection(
        name=GEMINI_CONNECTION,
        secrets={
            "api_key": api_key
        },  # The 'api_key' will be accessed by gemini_llm_invocation.py
        configs={
            "base_url": base_url
        },  # The 'base_url' will be accessed by gemin_llm_invocation.py
        description=f"HUIT AI Services Gemini API Connection via {base_url}",
    )
    return connection


def get_promptflow_client() -> PFClient:
    client = get_pf_client()
    return client
