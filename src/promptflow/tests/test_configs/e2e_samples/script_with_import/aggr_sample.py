from promptflow import tool, log_metric


@tool
def my_python_tool(prompts: list):
    assert isinstance(prompts, list)
    assert all(isinstance(p, str) for p in prompts)
    log_metric("dummy_metric", 1, variant_id="variant_0")
