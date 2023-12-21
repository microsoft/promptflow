from promptflow import tool

from passthrough import passthrough_str_and_wait_sync


@tool
def flow_entry(input1: str, wait_seconds=3):
    val1 = passthrough_str_and_wait_sync(input1, wait_seconds)
    val2 = passthrough_str_and_wait_sync(input1, wait_seconds + 2)
    return {"val1": val1, "val2": val2}
