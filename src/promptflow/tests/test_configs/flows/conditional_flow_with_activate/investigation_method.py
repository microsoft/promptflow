from promptflow import tool


@tool
def choose_investigation_method(method1: str, method2: str):
  method = {}
  if method1:
    method["first"] = method1
  if method2:
    method["second"] = method2
  return method