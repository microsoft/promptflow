from promptflow import tool
import json
import re

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(input1: str) -> str:
    input1 = re.sub(r'[$\\!]', '', input1)
    try:
        json_answer = json.loads(input1)
        answer = json_answer['answer']
    except Exception:
        answer = input1

    return answer
