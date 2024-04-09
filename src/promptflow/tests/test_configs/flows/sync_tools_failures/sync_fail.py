from promptflow.core import tool

def raise_exception(s):
    msg = f"In raise_exception: {s}"
    raise Exception(msg)


@tool
def raise_an_exception(s: str):
    try:
        raise_exception(s)
    except Exception as e:
        raise Exception(f"In tool raise_an_exception: {s}") from e
