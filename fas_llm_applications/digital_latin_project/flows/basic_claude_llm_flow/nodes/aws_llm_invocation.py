import boto3
import sys
import os
import json
from promptflow.core import tool
from promptflow.connections import CustomConnection as PFCustomConnection
from botocore.exceptions import ClientError
from fas_llm_applications._connections_manager_.common_secrets_loader import get_env_var
from fas_llm_applications._connections_manager_.aws_connection_utils import ensure_promptflow_aws_connection
from typing import Optional
from enum import Enum

BEDROCK_CONNECTION_NAME = "aws_bedrock_connection"
BEDROCK_SERVICE_NAME = "bedrock-runtime"
CLAUDE_3_7_SONNET_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
CLAUDE_4_SONNET_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
DEEPSEEK_MODEL_ID = "us.deepseek.r1-v1:0"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4000

CLAUDE3 = "Claude-3.7-Sonnet"
CLAUDE4 = "Claude-4.0-Sonnet"
DEEPSEEK = "DeepSeek"

@tool
def invoke_bedrock_llm(
    connection: PFCustomConnection,
    prompt: str,  # This will be the user prompt
    system_prompt: str,  # System prompt input
    model_name: str = "Claude3",
    max_tokens: Optional[int] = DEFAULT_MAX_TOKENS,
    temperature: Optional[float] = DEFAULT_TEMPERATURE,
) -> dict:
    """
    Invokes a specified LLM model via AWS Bedrock Runtime.
    This method dynamically constructs the payload based on the model_id
    to support models like Claude and Deepseek.

    Args:
        connection (CustomConnection): The PromptFlow custom connection containing
                                    AWS credentials (access_key_id, secret_access_key)
                                    and region_name.
        prompt (str): The user's query or prompt.
        system_prompt (str): The system-level instructions or persona for the LLM.
        model_name (str): The specific Bedrock model ID.
        max_token: (int, Optional): The maximum tokens for input and ouput combined
        temperature: (float, Optional): A parameter to set randomness of model response
        connection (CustomConnection): The PromptFlow custom connection containing
                                       AWS credentials (access_key_id, secret_access_key)
                                       and region_name.

    Returns:
        dict: A dictionary containing the LLM's response and potentially other metadata.
    """
    success = False
    model_id = get_model_id(model_name)
    try:
        # Retrieve AWS credentials and region from the PromptFlow CustomConnection
        print("Checking for Exisitng Connection")
        aws_access_key_id = connection.secrets.get("aws_access_key_id")
        aws_secret_access_key = connection.secrets.get("aws_secret_access_key")
        aws_region = connection.configs.get(
            "region_name", "us-east-1"
        )  # Default to us-east-1 if not specified

        if not aws_access_key_id or not aws_secret_access_key:
            raise ValueError(
                "AWS access_key_id or secret_access_key not found in the Bedrock connection."
            )
        else:
            print(f"Found existing connections: key - {aws_access_key_id}")

        # Initialize Bedrock Runtime client
        bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        print("Initialized the Bedrock Runtime Client")

        # Prepare the request body based on the model_id
        body = {}
        llm_text_response = ""
        full_api_response = {}

        if "claude" in model_id.lower():
            # Claude models (e.g., anthropic.claude-3-sonnet-20240229-v1:0)
            messages = []
            messages.append({"role": "user", "content": prompt})

            body = {
                "system": system_prompt if system_prompt else "",
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens if max_tokens else 4000,
                "temperature": temperature if temperature else 0.7,  # Adjust as needed
                "messages": messages,
            }
            # Claude's response format is different, it's a list of content blocks
            # We'll parse it after the invoke_model call

        elif "deepseek" in model_id.lower():
            # Deepseek models (e.g., deepseek-llm-v2)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            body = {
                "messages": messages,
                "max_tokens": max_tokens if max_tokens else 4000,  # Adjust as needed
                "temperature": temperature if temperature else 0.7,  # Adjust as needed
                "top_p": 1.0,  # Adjust as needed
                "stop": [],  # Adjust as needed
            }
            # Deepseek's response format is similar to OpenAI chat completions

        print(f"Invoking Bedrock model: {model_id} in region {aws_region}")
        print(f"Request Body: {json.dumps(body, indent=2)}")

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
            if full_api_response.get("choices") and full_api_response["choices"][0].get(
                "message"
            ):
                llm_text_response = full_api_response["choices"][0]["message"].get(
                    "content", ""
                )

        success = True

        # For the 'prompt_id' requested in the report, use a simple hash of the user prompt.
        prompt_id_for_report = f"user_query_{hash(prompt) % 10000}"

        return {
            "success": success,
            "response_text": llm_text_response,
            "full_api_response": full_api_response,
            "model_id_used": model_id,
            "prompt_id": prompt_id_for_report,  # Include prompt_id here for reporting
        }

    except ClientError as e:
        print(f"Bedrock Client Error: {e.response['Error']['Message']}")
        return {
            "error": f"Bedrock Client Error: {e.response['Error']['Message']}",
            "status": "failed",
        }
    except ValueError as e:
        print(f"Configuration or Payload Error: {e}")
        return {"error": f"Configuration or Payload Error: {e}", "status": "failed"}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {"error": f"An unexpected error occurred: {e}", "status": "failed"}


def get_model_id(model_name: str):
    if model_name == "Claude3":
        return CLAUDE_3_7_SONNET_MODEL_ID
    if model_name == "Claude4":
        return CLAUDE_4_SONNET_MODEL_ID
    if model_name == "DeepSeek":
        return DEEPSEEK_MODEL_ID


def create_aws_connection() -> PFCustomConnection:
    aws_access_key = get_env_var("AWS_AI_WORKFLOW_CORE_DEV_ID")
    aws_secret_key = get_env_var("AWS_AI_WORKFLOW_CORE_DEV_SECRET")
    aws_region = get_env_var("AWS_DEFAULT_REGION") or "us-east-1"

    pf_aws_connection = ensure_promptflow_aws_connection(
        access_key=aws_access_key,
        secret_key=aws_secret_key,
        region=aws_region,
        conn_name=BEDROCK_CONNECTION_NAME,
        service_name=BEDROCK_SERVICE_NAME,
    )
    return pf_aws_connection
