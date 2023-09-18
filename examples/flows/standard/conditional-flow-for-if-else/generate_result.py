from promptflow import tool


@tool
def generate_result(llm_result="", default_result="") -> str:
    if llm_result:
        return llm_result
    else:
        return default_result
