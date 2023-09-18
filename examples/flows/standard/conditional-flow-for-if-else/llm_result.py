from promptflow import tool


@tool
def llm_result(question: str) -> str:
    return (
        "Prompt flow is a suite of development tools designed to streamline "
        "the end-to-end development cycle of LLM-based AI applications."
    )
