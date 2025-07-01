from promptflow.core import tool
from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
)

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def evaluate_with_llm(
    judge_prompt_template_path: str,
    original_passage_text: str, # llm_output[user_prompt_used]
    original_llm_response_text: str # llm_output[response_text]
) -> str:
    
    # TODO: Add this into a jinja rendering utility.
    # Set up Jinja2 environment to load templates from the project root
    env = Environment(
        loader=FileSystemLoader(PROJECT_ROOT_FOR_TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
    )
    
    rendered_judge_prompt = ""

    # Basic input validation for paths
    if not judge_prompt_template_path:
        error_msg = "LLM as Judge prompt template path cannot be empty."
        return {"error": error_msg, "status": "failed"}

    try:
        # Render System Prompt Template
        judge_template = env.get_template(judge_prompt_template_path)

    except Exception as e:
        return {"error": f"Failed to render Jinja template(s): {e}", "status": "failed"}
