import os
import sys
import pandas as pd
from promptflow.core import tool
from fas_llm_applications.digital_latin_project.utilities.prompt_registry_util import get_system_prompt, get_user_prompt, get_judge_prompt
from typing import Dict, Any, Optional
from pathlib import Path
import json

PROMPT_TEMPLATES_BASE_PATH = "fas_llm_applications/digital_latin_project/prompts/"
RESULTS_BASE_PATH = "fas_llm_applications/digital_latin_project/results/"

@tool
def prompt_selector(
    system_prompt_id: Optional[str] = None,
    user_prompt_id: Optional[str] = None,
    judge_prompt_id: Optional[str] = None,
    judge_user_prompt_id: Optional[str] = None,
    report_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Selects the appropriate Jinja template paths and default template variables
    based on a given prompt identifiers. All arguments are optional, but at least one must be provided.

    Args:
        system_prompt_id (str, optional): A unique identifier for the desired system prompt.
        user_prompt_id (str, optional): A unique identifier for the desired user prompt.
        judge_prompt_id (str, optional): A unique identifier for the desired judge system prompt.
        judge_user_prompt_id (str, optional): A unique identifier for the desired judge user prompt.

    Returns:
        Dict[str, Any]: A dictionary containing:
            - 'user_prompt_template_path' (str): Path to the user Jinja template (if user_prompt_id provided).
            - 'system_prompt_template_path' (str): Path to the system Jinja template (if system_prompt_id provided).
            - 'judge_prompt_template_path' (str): Path to the judge system Jinja template (if judge_prompt_id provided).
            - 'judge_user_prompt_template_path' (str): Path to the judge user Jinja template (if judge_user_prompt_id provided).
            - 'template_variables' (dict): Default variables for the templates.
    """
    prompt_config = {}

    # Define subfolder paths for clarity
    SYSTEM_PROMPT_DIR = os.path.join(PROMPT_TEMPLATES_BASE_PATH, "system")
    USER_PROMPT_DIR = os.path.join(PROMPT_TEMPLATES_BASE_PATH, "user")
    JUDGE_SYSTEM_PROMPT_DIR = os.path.join(PROMPT_TEMPLATES_BASE_PATH, "judge/system")
    JUDGE_USER_PROMPT_DIR = os.path.join(PROMPT_TEMPLATES_BASE_PATH, "judge/user")

    # Fail if all are None
    if not (system_prompt_id or user_prompt_id or judge_prompt_id or judge_user_prompt_id):
        raise ValueError("At least one of system_prompt_id, user_prompt_id, judge_prompt_id, or judge_user_prompt_id must be provided.")

    try:
        system_prompt_filename = None
        user_prompt_filename = None
        judge_system_prompt_filename = None
        judge_user_prompt_filename = None
        # Only fetch if provided
        if system_prompt_id:
            system_prompt_filename = get_system_prompt(key=system_prompt_id)
        if user_prompt_id:
            user_prompt_filename = get_user_prompt(key=user_prompt_id)
        if judge_prompt_id:
            judge_system_prompt_filename = get_judge_prompt(key=judge_prompt_id, prompt_type="system")
        if judge_user_prompt_id:
            judge_user_prompt_filename = get_judge_prompt(key=judge_user_prompt_id, prompt_type="user")

        # Create empty dictionary for template variables
        template_variables = {}

        # Gather template variables from prompt data
        script_dir = Path(__file__).parent
        prompt_data_base_path = script_dir / "../data/prompt_data"
        prompt_data_base_path = prompt_data_base_path.resolve()
        template_variables = {}
        try:
            csv_files = list(prompt_data_base_path.glob("*.csv"))
            if not csv_files:
                raise FileNotFoundError(f"No CSV files found in prompt data folder: {prompt_data_base_path}")
            for file_path in csv_files:
                key = file_path.stem
                data_frame = pd.read_csv(file_path)
                text_data = data_frame.to_csv(index=False)
                template_variables[key] = text_data
        except Exception as e:
            print(f"Error reading prompt data files: {e}")

        # If report_id is provided, load the JSON and extract fields as template variables
        if report_id is not None:
            report_path = script_dir.parent / "results" / f"llm_report_{report_id:05}.json"
            if report_path.exists():
                try:
                    with open(report_path, encoding="utf8") as f:
                        report_data = json.load(f)
                    # Extract common fields
                    template_variables["original_passage_text"] = report_data.get("user_prompt_used", "")
                    llm_invocation_output = report_data.get("llm_invocation_output", {})
                    template_variables["original_llm_response_text"] = llm_invocation_output.get("response_text", "")
                    template_variables["system_prompt_id"] = report_data.get("system_prompt_id", "")
                    template_variables["user_prompt_id"] = report_data.get("user_prompt_id", "")
                    # Add any other fields you want to expose to templates here
                except Exception as e:
                    print(f"Error reading report JSON for report_id {report_id}: {e}")
            else:
                print(f"Report file not found for report_id {report_id}: {report_path}")

        # Build Prompt Config
        if system_prompt_filename:
            prompt_config["system_prompt_template_path"] = os.path.join(SYSTEM_PROMPT_DIR, system_prompt_filename)
        if user_prompt_filename:
            prompt_config["user_prompt_template_path"] = os.path.join(USER_PROMPT_DIR, user_prompt_filename)
        if judge_system_prompt_filename:
            prompt_config["judge_prompt_template_path"] = os.path.join(JUDGE_SYSTEM_PROMPT_DIR, judge_system_prompt_filename)
        if judge_user_prompt_filename:
            prompt_config["judge_user_prompt_template_path"] = os.path.join(JUDGE_USER_PROMPT_DIR, judge_user_prompt_filename)
        prompt_config["template_variables"] = template_variables
        return prompt_config

    except Exception as e:
        raise ValueError(f"An issue arose during prompt selection: {e}")