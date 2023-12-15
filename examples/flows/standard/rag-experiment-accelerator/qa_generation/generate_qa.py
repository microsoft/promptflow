from promptflow import tool
from rag_experiment_accelerator.run.qa_generation import run


@tool
def my_python_tool(config_dir: str, should_generate_qa:bool) -> bool:
    if should_generate_qa:
        run(config_dir)
    return True
