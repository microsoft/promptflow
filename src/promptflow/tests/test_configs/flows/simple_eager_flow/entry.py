from promptflow import flow, trace
import time
# from passthrough import passthrough_str_and_wait_sync

@trace
def passthrough_str_and_wait_sync(input1: str, wait_seconds=3) -> str:
    assert isinstance(input1, str), f"input1 should be a string, got {input1}"
    print("Wait for", wait_seconds, "seconds in sync function")
    for i in range(wait_seconds):
        print(i)
        time.sleep(1)
    return input1


@flow
def flow_entry(input1: str, wait_seconds=3):
    val1 = passthrough_str_and_wait_sync(input1, wait_seconds)
    val2 = passthrough_str_and_wait_sync(input1, wait_seconds + 2)
    return {"val1": val1, "val2": val2}
