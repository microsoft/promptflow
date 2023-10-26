from promptflow import tool

def contains(metric: str, metric_list: str):
  lowered = [s.lower() for s in metric_list]
  return metric.lower() in lowered

@tool
def require(metric_list: list) -> str:
  return contains("groundedness", metric_list)