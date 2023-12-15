from promptflow import tool
from rag_experiment_accelerator.run.evaluation import run


@tool
def my_python_tool(config_dir: str) -> bool:
    run(config_dir)
    return True
