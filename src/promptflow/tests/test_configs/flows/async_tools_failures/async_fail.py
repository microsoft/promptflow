from promptflow.core import tool

async def raise_exception_async(s):
    msg = f"In raise_exception_async: {s}"
    raise Exception(msg)


@tool
async def raise_an_exception_async(s: str):
    try:
        await raise_exception_async(s)
    except Exception as e:
        raise Exception(f"In tool raise_an_exception_async: {s}") from e
