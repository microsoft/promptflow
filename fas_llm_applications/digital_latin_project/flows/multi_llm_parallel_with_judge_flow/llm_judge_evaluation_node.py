import os
import sys
import json
import fcntl
from datetime import datetime
from promptflow.core import tool
from jinja2 import Environment, FileSystemLoader, select_autoescape
from fas_llm_applications.digital_latin_project.flows.multi_llm_parallel_flow.nodes.multi_llm_invocation import invoke_llm

# Always resolve EVAL_RESULTS_DIR under digital_latin_project
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
EVAL_RESULTS_DIR = os.path.join(PROJECT_ROOT, 'digital_latin_project', 'evaluation', 'llm_as_judge_results')
EVAL_COUNTER_FILE = os.path.join(EVAL_RESULTS_DIR, 'evaluation_report_counter.txt')
# Update MAIN_RESULTS_DIR to the correct absolute path
MAIN_RESULTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../results'))
if not os.path.exists(MAIN_RESULTS_DIR):
    # Try the digital_latin_project/results path if not found
    MAIN_RESULTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../results'))
    if not os.path.exists(MAIN_RESULTS_DIR):
        MAIN_RESULTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../digital_latin_project/results'))

os.makedirs(EVAL_RESULTS_DIR, exist_ok=True)

def _get_next_eval_id(counter_file_path: str) -> int:
    for _ in range(10):
        try:
            with open(counter_file_path, "a+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.seek(0)
                content = f.read().strip()
                current_id = int(content) if content.isdigit() else 0
                next_id = current_id + 1
                f.seek(0)
                f.truncate()
                f.write(str(next_id))
                fcntl.flock(f, fcntl.LOCK_UN)
            return next_id
        except Exception as e:
            sys.stderr.write(f"[EVAL COUNTER] Error: {e}\n")
    raise RuntimeError("Failed to get next evaluation report ID.")

@tool
def evaluate_with_llm(
    judge_prompt_template_path: str,
    judge_user_prompt_template_path: str,
    model_id: str,
    template_variables: dict,
    original_llm_results_report_id: int = None,
    original_passage_text: str = None,
    original_llm_response_text: str = None
) -> dict:
    # Input validation
    has_report_id = original_llm_results_report_id is not None
    has_passage_and_response = original_passage_text is not None and original_llm_response_text is not None
    if (has_report_id and has_passage_and_response) or (not has_report_id and not has_passage_and_response):
        sys.stderr.write("You must provide either original_llm_results_report_id OR (original_passage_text AND original_llm_response_text), but not both.\n")
        return {"error": "Invalid input combination.", "status": "failed"}

    # Load from main results if report_id is given
    system_prompt_id = user_prompt_id = None
    if has_report_id:
        report_path = os.path.join(MAIN_RESULTS_DIR, f"llm_report_{original_llm_results_report_id:05}.json")
        if not os.path.exists(report_path):
            sys.stderr.write(f"Main result file not found: {report_path}\n")
            return {"error": "Main result file not found.", "status": "failed"}
        try:
            with open(report_path, encoding='utf8') as f:
                main_data = json.load(f)
            original_passage_text = main_data.get('user_prompt_used', '')
            # Robust extraction for Gemini-style nested structure
            def extract_llm_response(main_data):
                llm_output = main_data.get("llm_invocation_output", {})
                # Gemini format
                candidates = llm_output.get("candidates")
                if candidates and isinstance(candidates, list):
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts and isinstance(parts, list):
                        return parts[0].get("text", "")
                # Fallback for other models
                if "response_text" in llm_output:
                    return llm_output["response_text"]
                return ""
            original_llm_response_text = extract_llm_response(main_data)
            system_prompt_id = main_data.get('system_prompt_id', '')
            user_prompt_id = main_data.get('user_prompt_id', '')
        except Exception as e:
            sys.stderr.write(f"Failed to load or parse main result: {e}\n")
            return {"error": "Failed to load or parse main result.", "status": "failed"}

    # Prepare dynamic variables for the judge user prompt template
    dynamic_template_variables = {
        "original_passage_text": original_passage_text,
        "original_llm_response_text": original_llm_response_text
    }

    # Compose provenance user_prompt_id for evaluation
    provenance_user_prompt_id = f"combined_from_system_{system_prompt_id}_user_{user_prompt_id}"

    # Extract judge_prompt_id from the template path
    def extract_judge_prompt_id(template_path):
        filename = os.path.basename(template_path)
        return filename.split('_')[0]
    judge_prompt_id = extract_judge_prompt_id(judge_prompt_template_path)

    # Call LLM as judge using invoke_llm, and measure latency
    import time
    start_time = time.time()
    llm_result = invoke_llm(
        user_prompt_template_path=judge_user_prompt_template_path,
        system_prompt_template_path=judge_prompt_template_path,
        system_prompt_id=judge_prompt_id,  # Use the parsed judge_prompt_id
        user_prompt_id=provenance_user_prompt_id,
        model_id=model_id,
        selector_template_variables=template_variables,
        dynamic_template_variables=dynamic_template_variables
    )
    evaluation_latency = time.time() - start_time
    if llm_result.get("status") != "success":
        sys.stderr.write(f"Judge LLM invocation failed: {llm_result.get('error', 'Unknown error')}\n")
        return {"error": "Judge LLM invocation failed.", "status": "failed"}

    # Extract token usage metrics if available
    usage = {}
    api_response = llm_result.get("full_api_response", {})
    # Gemini: usageMetadata, Bedrock: usage
    if "usageMetadata" in api_response:
        usage = api_response["usageMetadata"]
    elif "usage" in api_response:
        usage = api_response["usage"]

    # Save evaluation result
    try:
        eval_id = _get_next_eval_id(EVAL_COUNTER_FILE)
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        eval_json = {
            "timestamp": now,
            "evaluation_report_id": eval_id,
            "original_report": {
                "report_id": original_llm_results_report_id if has_report_id else None,
                "system_prompt_id": system_prompt_id,
                "user_prompt_id": user_prompt_id,
            },
            "judge_prompts": {
                # "system_prompt_used": llm_result.get("system_prompt_used", ""),  # Commented out to avoid storing full prompt with CSV data
                "system_prompt_id": judge_prompt_id,
                "user_prompt_used": llm_result.get("user_prompt_used", ""),
                "user_prompt_id": os.path.basename(judge_user_prompt_template_path).split('_')[0] if judge_user_prompt_template_path else None,
            },
            "model": {
                "model_id": model_id,
            },
            "evaluation": {
                "llm_response": llm_result.get("response_text", ""),
                "token_usage": usage,
                "evaluation_latency": evaluation_latency,
                "full_api_response": api_response,
            }
        }
        eval_path = os.path.join(EVAL_RESULTS_DIR, f"evaluation_report_{eval_id:05}.json")
        with open(eval_path, "w", encoding="utf8") as f:
            json.dump(eval_json, f, indent=2)
        return {"status": "success", "evaluation_report_path": eval_path, "evaluation_report_id": eval_id}
    except Exception as e:
        sys.stderr.write(f"Failed to save evaluation report: {e}\n")
        return {"error": "Failed to save evaluation report.", "status": "failed"}
