import os
import json
import fcntl
import time
import uuid
import re
from datetime import datetime
from promptflow.core import tool

# Folder where reports will be saved
REPORT_FOLDER_NAME = "results"
# File where the last sequential report ID will be stored
REPORT_COUNTER_FILE = "report_counter.txt"


def _get_next_sequential_id(counter_file_path: str) -> int:
    """
    Reads, increments, and writes a sequential ID from a counter file.
    Includes basic file locking to prevent race conditions during concurrent access.
    """
    max_retries = 10
    retry_delay_sec = 0.1

    for attempt in range(max_retries):
        try:
            # Open file for reading and writing, create if it doesn't exist
            with open(counter_file_path, "a+") as f:
                # Acquire an exclusive lock (blocking)
                fcntl.flock(f, fcntl.LOCK_EX)

                f.seek(0)  # Go to the beginning of the file
                content = f.read().strip()

                current_id = 0
                if content.isdigit():
                    current_id = int(content)

                next_id = current_id + 1

                f.seek(0)  # Go to the beginning of the file to overwrite
                f.truncate()  # Clear existing content
                f.write(str(next_id))

                # Release the lock
                fcntl.flock(f, fcntl.LOCK_UN)
            return next_id
        except BlockingIOError:
            # If the lock is already held, wait and retry
            time.sleep(retry_delay_sec)
        except Exception as e:
            print(f"Error accessing sequential ID file on attempt {attempt+1}/{max_retries}: {e}")
            time.sleep(retry_delay_sec)  # Wait before retrying even on other errors

    raise RuntimeError(f"Failed to get next sequential ID after {max_retries} attempts due to persistent errors.")


@tool
def generate_run_report(
    system_prompt_id: str,
    user_prompt_id: str,
    llm_model_id: str,
    system_prompt_used: str,
    user_prompt_used: str,
    llm_invocation_output: dict,
    llm_run_time: float,
    flow_name: str,
    is_rag_flow: bool,
    batch_id: str = None,
    test_case_no: int = None
) -> dict:
    """
    Generates a comprehensive JSON report for a PromptFlow run.

    This function collects detailed information about an LLM invocation within a PromptFlow,
    including prompts, model details, invocation outputs, and performance metrics,
    and then saves this data into a sequentially numbered JSON file within a 'results' directory.

    Args:
        system_prompt_id (str): A unique identifier for the system prompt used in the LLM invocation.
        user_prompt_id (str): A unique identifier for the user prompt used in the LLM invocation.
        llm_model_id (str): The identifier of the specific LLM model that was invoked (e.g., 'gpt-4', 'claude-3').
        system_prompt_used (str): The exact text of the system prompt that was provided as an input to the flow.
        user_prompt_used (str): The exact text of the user prompt that was provided as an input to the flow.
        llm_invocation_output (dict): The complete raw output dictionary returned directly from the LLM invocation node.
                                      This typically includes the LLM's response, token counts, and other metadata.
        llm_run_time (float): The duration, in seconds, that the LLM took to process the query.
        flow_name (str): The name of the PromptFlow that executed this LLM invocation.
        is_rag_flow (bool): A boolean indicating whether this specific flow run involved a Retrieval Augmented Generation (RAG) process.
        batch_id (str, optional): An optional identifier for the batch run this invocation belongs to. Defaults to None.
        test_case_no (int, optional): An optional sequential number identifying a specific test case within a batch or test run. Defaults to None.

    Returns:
        dict: A dictionary containing details about the report generation, typically including
              a 'status' (e.g., 'success', 'failure') and 'report_path' to the generated file.
    """
    current_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Generate a report run_id
    report_run_id = None

    if not report_run_id:
        # Generate a more descriptive ID if no custom run_id is provided use selected_prompt_id
        selected_prompt_id = f"{system_prompt_id}__{user_prompt_id}"

        # Sanitize parts for filename safety
        sanitized_flow_name = re.sub(r'[^a-zA-Z0-9_.-]', '', flow_name.replace(' ', '_'))
        sanitized_prompt_id = re.sub(r'[^a-zA-Z0-9_.-]', '', selected_prompt_id.replace(' ', '_'))

        # Combine with a short UUID for uniqueness and a timestamp
        short_uuid_fragment = str(uuid.uuid4())[:8]
        report_run_id = f"auto_{sanitized_flow_name}_{sanitized_prompt_id}_{current_timestamp}_{short_uuid_fragment}"

    # Determine the base path for the results folder and counter file ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '../../..'))

    # The reports and counter file will be saved in fas_llm_applications/digital_latin_project/results
    results_folder_path = os.path.join(project_root, "fas_llm_applications",
                                       "digital_latin_project", REPORT_FOLDER_NAME)

    # Create the results directory if it doesn't exist
    os.makedirs(results_folder_path, exist_ok=True)

    # Get the next sequential ID
    counter_file_path = os.path.join(results_folder_path, REPORT_COUNTER_FILE)
    try:
        sequential_report_id = _get_next_sequential_id(counter_file_path)
    except RuntimeError as e:
        return {"status": "failed", "error_message": str(e)}

    # Define the output file name using the sequential report ID
    # Pad with leading zeros for consistent sorting in file explorer (e.g., 001, 002, 010)
    file_name = f"llm_report_{sequential_report_id:05d}.json"  # e.g., llm_report_00001.json
    file_path = os.path.join(results_folder_path, file_name)

    # --- Construct the report data ---
    report_data = {
        "timestamp": current_timestamp,
        "report_id": sequential_report_id,  # Now using the sequential ID
        "report_filename": file_name,
        "test_batch_id": batch_id if batch_id else "None",
        "test_case_no": test_case_no,
        "system_prompt_id": system_prompt_id,
        "user_prompt_id": user_prompt_id,
        "model_used": llm_model_id,
        "system_prompt_used": system_prompt_used,
        "user_prompt_used": user_prompt_used,
        "llm_invocation_output": llm_invocation_output,
        "llm_latency_in_sec": llm_run_time,
        "flow_metadata": {
            "flow_name": flow_name,
            "flow_run_id": report_run_id,
            "is_rag_flow": is_rag_flow,
            "report_generated_by_node": "report_generator_node"
        }
    }

    try:
        # Save the report data to a JSON file
        with open(file_path, "w") as f:
            json.dump(report_data, f, indent=4)
        print(f"Report successfully saved to: {file_path}")
        return {"status": "success", "report_path": file_path, "report_id": sequential_report_id}
    except Exception as e:
        print(f"Error saving report: {e}")
        return {"status": "failed", "error_message": str(e)}
