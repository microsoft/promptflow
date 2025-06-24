import json
from promptflow.core import tool
from promptflow.connections import CustomConnection
import boto3
from botocore.exceptions import ClientError

@tool
def invoke_bedrock_llm(
    prompt: str, # This will be the user prompt
    system_prompt: str, # System prompt input
    model_id: str,
    connection: CustomConnection # This will be your AWS Bedrock connection
) -> dict:
    """
    Invokes a specified LLM model via AWS Bedrock Runtime.
    This method dynamically constructs the payload based on the model_id
    to support models like Claude and Deepseek.

    Args:
        prompt (str): The user's query or prompt.
        system_prompt (str): The system-level instructions or persona for the LLM.
        model_id (str): The specific Bedrock model ID.
        connection (CustomConnection): The PromptFlow custom connection containing
                                       AWS credentials (access_key_id, secret_access_key)
                                       and region_name.

    Returns:
        dict: A dictionary containing the LLM's response and potentially other metadata.
    """
    try:
        # Retrieve AWS credentials and region from the PromptFlow CustomConnection
        aws_access_key_id = connection.secrets.get("aws_access_key_id")
        aws_secret_access_key = connection.secrets.get("aws_secret_access_key")
        aws_region = connection.configs.get("region_name", "us-east-1") # Default to us-east-1 if not specified

        if not aws_access_key_id or not aws_secret_access_key:
            raise ValueError("AWS access_key_id or secret_access_key not found in the Bedrock connection.")

        # Initialize Bedrock Runtime client
        bedrock_runtime = boto3.client(
            service_name='bedrock-runtime',
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )

        # Prepare the request body based on the model_id
        body = {}
        llm_text_response = ""
        full_api_response = {}

        if "claude" in model_id.lower():
            # Claude models (e.g., anthropic.claude-3-sonnet-20240229-v1:0)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000, # Can be adjust as needed
                "messages": messages
            }
            
        elif "deepseek" in model_id.lower():
            # Deepseek models (e.g., deepseek-llm-v2)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            body = {
                "messages": messages,
                "max_tokens": 4000, # Adjust as needed
                "temperature": 0.7, # Adjust as needed
                "top_p": 1.0, # Adjust as needed
                "stop": [] # Adjust as needed
            }
            # Deepseek's response format is similar to OpenAI chat completions
            
        print(f"Invoking Bedrock model: {model_id} in region {aws_region}")
        print(f"Request Body: {json.dumps(body, indent=2)}")

        response = bedrock_runtime.invoke_model(
            body=json.dumps(body),
            modelId=model_id,
            accept='application/json',
            contentType='application/json'
        )

        full_api_response = json.loads(response['body'].read())

        # Parse response based on model type
        if "claude" in model_id.lower():
            if full_api_response.get("content"):
                for content_block in full_api_response["content"]:
                    if content_block.get("type") == "text":
                        llm_text_response += content_block["text"]
            
        elif "deepseek" in model_id.lower():
            if full_api_response.get("choices") and full_api_response["choices"][0].get("message"):
                llm_text_response = full_api_response["choices"][0]["message"].get("content", "")
            
        elif "titan" in model_id.lower():
            if full_api_response.get("results"):
                llm_text_response = full_api_response["results"][0].get("outputText", "")
        
        # For the 'prompt_id' requested in the report, use a simple hash of the user prompt.
        prompt_id_for_report = f"user_query_{hash(prompt) % 10000}" 

        return {
            "response_text": llm_text_response,
            "full_api_response": full_api_response,
            "model_id_used": model_id,
            "prompt_id": prompt_id_for_report # Include prompt_id here for reporting
        }

    except ClientError as e:
        return {"error": f"Bedrock Client Error: {e.response['Error']['Message']}", "status": "failed"}
    except ValueError as e:
        return {"error": f"Configuration or Payload Error: {e}", "status": "failed"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}", "status": "failed"}
