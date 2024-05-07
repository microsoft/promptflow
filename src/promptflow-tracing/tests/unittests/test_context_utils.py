import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

import pytest

from promptflow.tracing import ThreadPoolExecutorWithContext


@pytest.mark.unittest
def test_thread_pool_executor_with_context():
    var = contextvars.ContextVar("var", default="default_value")
    var.set("value_in_parent")
    with ThreadPoolExecutor() as executor:
        assert executor.submit(var.get).result() == "default_value"
    with ThreadPoolExecutorWithContext() as executor:
        assert executor.submit(var.get).result() == "value_in_parent"
    with ThreadPoolExecutorWithContext(initializer=var.set, initargs=("value_in_initializer",)) as executor:
        assert executor.submit(var.get).result() == "value_in_initializer"


@pytest.mark.unittest
@pytest.mark.asyncio
async def test_thread_pool_executor_with_context_async():
    var = contextvars.ContextVar("var", default="default_value")
    var.set("value_in_parent")
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, var.get)
    assert result == "default_value"
    result = await loop.run_in_executor(ThreadPoolExecutorWithContext(), var.get)
    assert result == "value_in_parent"
    initargs = ("value_in_initializer",)
    result = await loop.run_in_executor(ThreadPoolExecutorWithContext(initializer=var.set, initargs=initargs), var.get)
    assert result == "value_in_initializer"
