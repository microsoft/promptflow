from promptflow.core import tool


@tool
def choose_investigation_method(method1="Skip job info extractor", method2="Skip incident info extractor"):
    method = {}
    if method1:
        method["first"] = method1
    if method2:
        method["second"] = method2
    return method
