
from promptflow.core import tool
import re

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need


def extract_ans(ans_model):
    ans_model = ans_model.split("\n")
    ans = []
    residual = []
    for li, al in enumerate(ans_model):
        ans.append(al)
        if "answer is" in al:
            break
    residual = list(ans_model[li + 1 :])
    ans = "\n".join(ans)
    residual = "\n".join(residual)
    return ans, residual


def get_result(text: str):
    pattern = r"\d*\.?\d+"
    res = re.findall(pattern, text)
    # return res[-1].replace(".00", "") if res else ""
    return res[-1] if res else ""


def test_answer(pred_str, ans_str):
    pred, gold = get_result(pred_str), get_result(ans_str)
    return pred == gold


@tool
def my_python_tool(llm_response: str, answer: str) -> int:
    print("LLM response: ", llm_response)
    print("Ground Truth Answer: ", answer)
    ans_, residual = extract_ans(llm_response)
    model_ans = ans_.replace("Q:", "").replace("A:", "")
    if test_answer(model_ans, answer):
        return 1
    return 0
