from promptflow import tool


@tool
def llm_result(question: str) -> str:
    # You can use an LLM node to replace this tool.
    return (
        "Prompt flow is a suite of development tools designed to streamline "
        "the end-to-end development cycle of LLM-based AI applications."
    )
