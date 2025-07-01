import os
import pandas as pd
from promptflow.core import tool
from fas_llm_applications.digital_latin_project.utilities.prompt_registry_util import get_system_prompt, get_user_prompt
from typing import Dict, Any
from pathlib import Path

PROMPT_TEMPLATES_BASE_PATH = "fas_llm_applications/digital_latin_project/prompts/"

@tool
def prompt_selector(
    system_prompt_id: str,
    user_prompt_id: str
) -> Dict[str, Any]:
    """
    Selects the appropriate Jinja template paths and default template variables
    based on a given prompt identifiers.

    Args:
        system_prompt_id (str): A unique identifier for the desired system prompt.
        user_prompt_id (str): A unique identifier for the desired user prompt.

    Returns:
        Dict[str, Any]: A dictionary containing:
            - 'user_prompt_template_path' (str): Path to the user Jinja template.
            - 'system_prompt_template_path' (str): Path to the system Jinja template.
            - 'template_variables' (dict): Default variables for the templates.
    """
    prompt_config = {}

    # Define subfolder paths for clarity
    SYSTEM_PROMPT_DIR = os.path.join(PROMPT_TEMPLATES_BASE_PATH, "system")
    USER_PROMPT_DIR = os.path.join(PROMPT_TEMPLATES_BASE_PATH, "user")

    try: 
        # Validate param and Get system prompt filename
        system_prompt_filename = get_system_prompt(key=system_prompt_id)

        # Validate parma and Get user prompt filename
        user_prompt_filename = get_user_prompt(key=user_prompt_id)

        # TODO: Additional prompt configurations to be added for the judge as LLM prompts

        # Create empty dictionary for template variables
        template_variables = {}

        # Gather template variables from prompt data
        ## Path to prompt data
        prompt_data_base_path = "fas_llm_applications/digital_latin_project/data/prompt_data"

        ## For each file in the prompt data file path, use the file name to add a key in the dictionary
        for file_path in Path(prompt_data_base_path).glob("*.csv"):
            # Use the file name (without extensions) as key
            key = file_path.stem  #example dcc_words from dcc_words.csv

            # Add a value as the file content (converted to text)
            data_frame = pd.read_csv(file_path)
            text_data = data_frame.to_csv(index=False)
            print(f"For `{key}` data, value 10 character preview: [`{text_data[:10]}`]")
            template_variables[key] = data_frame.to_csv(index=False)

        ## Build Prompt Config
        prompt_config = {
            "system_prompt_template_path": os.path.join(SYSTEM_PROMPT_DIR, system_prompt_filename), # Now in 'system' subfolder
            "user_prompt_template_path": os.path.join(USER_PROMPT_DIR, user_prompt_filename), # Now in 'user' subfolder
            "template_variables": template_variables
        }
        return prompt_config
    
    except Exception as e:
        raise ValueError(f"An issue arose during prompt selection: {e}")