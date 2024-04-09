import typing

from promptflow.core import log_metric, tool


@tool
def log_metrics(numbers: typing.List[typing.Dict]):
    print(numbers)
    log_metric(key="nan_metrics", value=float("nan"))
    log_metric(key="inf_metrics", value=float("inf"))
