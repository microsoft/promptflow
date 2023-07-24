import os

from promptflow import tool


@tool
def my_python_tool(prompt: str) -> str:
    def asset_val(val, prefix=None):
        assert val is not None
        assert not val.startswith("$")
        if prefix:
            assert val.lower().startswith(prefix)
    asset_val(os.environ.get("OPENAI_API_BASE"), "https://")
    asset_val(os.environ.get("OPENAI_API_KEY"))
    asset_val(os.environ.get("OPENAI_API_TYPE"), "azure")
    asset_val(os.environ.get("OPENAI_API_VERSION"))
    return prompt