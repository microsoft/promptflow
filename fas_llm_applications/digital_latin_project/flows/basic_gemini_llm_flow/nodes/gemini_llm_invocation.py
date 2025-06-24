import json
import sys
import os
import requests
import time
from promptflow.core import tool
from promptflow.connections import CustomConnection
from jinja2 import Environment, FileSystemLoader, select_autoescape

PROJECT_ROOT_FOR_TEMPLATES = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../../")
)

@tool
def invoke_gemini_huit_llm(
    connection: CustomConnection,
    user_prompt_template_path: str,
    system_prompt_template_path: str,
    prompt_id: str,
    model_id: str,
    selector_template_variables: dict = {},
    dynamic_template_variables: dict = {},
    temperature: float = 0.7,
    max_tokens: int = 4000,
) -> dict:
    """
    Invokes the Google Gemini model via the HUIT AI Services API Gateway.
    It renders Jinja templates for prompts before invoking the LLM.

    Args:
        connection (CustomConnection): The PromptFlow custom connection containing
                                    the HUIT API key and base URL.
        user_prompt_template_path (str): Relative path to the Jinja template file for the user prompt.
        system_prompt_template_path (str): Relative path to the Jinja template file for the system prompt.
        template_variables (dict): A dictionary of variables to pass to the Jinja templates for rendering.
        prompt_id (str): A unique identifier for the specific prompt definition/iteration.
        model_id (str): The specific Gemini model ID.
        selector_template_variables: (dict) = Variables from the prompt selector node,
        dynamic_template_variables: (dict) = Dynamic variables from the input node,
        temperature (float): The sampling temperature to use for text generation.
        max_tokens (int): The maximum number of tokens to generate.
    Returns:
        dict: A dictionary containing the LLM's response and other metadata.
              Includes the *rendered* prompts used for reporting, and the prompt_id.
    """
    print(f"DEBUG: Rendering prompts from templates in {PROJECT_ROOT_FOR_TEMPLATES}")

    # NEW: Merge template variables within the Python tool
    # Dynamic variables take precedence over selector variables
    merged_template_variables = {
        **selector_template_variables,
        **dynamic_template_variables,
    }
    print(f"DEBUG: Merged template variables: {merged_template_variables}")

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
        raise RuntimeError("ERROR: Failed to render Jinja template(s) from paths '{user_prompt_template_path}' and '{system_prompt_template_path}': {e}")

    try:
        # Retrieve API key and base URL from the PromptFlow CustomConnection
        api_key = connection.secrets.get("api_key")
        base_url = connection.configs.get(
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
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        # Add system_instruction at the top level if a system prompt is provided
        if rendered_system_prompt:
            payload["system_instruction"] = {
                "parts": [{"text": rendered_system_prompt}]
            }

        headers = {"Content-Type": "application/json", "api-key": api_key}

        print(f"Invoking Gemini model: {model_id} via {api_endpoint}")

        start_time = time.time()
        response = requests.post(api_endpoint, headers=headers, json=payload)
        response.raise_for_status()

        response_json = response.json()
        end_time = time.time()
        duration = end_time - start_time

        llm_text_response = ""
        if response_json and response_json.get("candidates"):
            for candidate in response_json["candidates"]:
                if candidate.get("content") and candidate["content"].get("parts"):
                    for part in candidate["content"]["parts"]:
                        if part.get("text"):
                            llm_text_response += part["text"]

        # Use the prompt_id passed as input directly
        return {
            "response_text": llm_text_response,
            "full_api_response": response_json,
            "model_id_used": model_id,
            "prompt_id": prompt_id,  # Use the prompt_id from input
            "user_prompt_used": rendered_user_prompt,  # Return the RENDERED user prompt
            "system_prompt_used": rendered_system_prompt,  # Return the RENDERED system prompt
            "llm_run_time": duration,
            "status": "success",
        }

    except requests.exceptions.RequestException as e:
        return {"error": f"HTTP Request failed: {e}", "status": "failed"}
    except ValueError as e:
        return {"error": f"Configuration error: {e}", "status": "failed"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}", "status": "failed"}
