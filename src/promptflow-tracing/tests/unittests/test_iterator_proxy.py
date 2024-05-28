from types import AsyncGeneratorType, GeneratorType
from typing import AsyncIterator, Iterator

import pytest

from promptflow.tracing.contracts.iterator_proxy import AsyncIteratorProxy, IteratorProxy


def generator():
    for i in range(3):
        yield i


def iterator():
    return iter([0, 1, 2])


@pytest.mark.unittest
def test_generator_proxy_next():
    proxy = IteratorProxy(generator())
    assert proxy.items == []
    assert next(proxy) == 0
    assert next(proxy) == 1
    assert next(proxy) == 2

    with pytest.raises(StopIteration):
        next(proxy)

    assert proxy.items == [0, 1, 2]


@pytest.mark.unittest
def test_generator_proxy_iter():
    original_generator = generator()
    proxy = IteratorProxy(generator())

    for num in proxy:
        assert num == next(original_generator)

    assert proxy.items == [0, 1, 2]


@pytest.mark.unittest
def test_iterator_proxy_next():
    proxy = IteratorProxy(iterator())
    assert proxy.items == []
    assert next(proxy) == 0
    assert next(proxy) == 1
    assert next(proxy) == 2

    with pytest.raises(StopIteration):
        next(proxy)

    assert proxy.items == [0, 1, 2]


@pytest.mark.unittest
def test_iterator_proxy_iter():
    original_iterator = iterator()
    proxy = IteratorProxy(iterator())

    for num in proxy:
        assert num == next(original_iterator)

    assert proxy.items == [0, 1, 2]


@pytest.mark.unittest
def test_generator_proxy_type():
    """
    Test that GeneratorProxy is a subclass of Iterator but not GeneratorType
    """
    proxy = IteratorProxy(generator())
    # GeneratorProxy is a subclass of Iterator
    assert isinstance(proxy, Iterator), "proxy should be an instance of Iterator"
    # GeneratorProxy is not a subclass of GeneratorType
    assert not isinstance(proxy, GeneratorType), "proxy should not be an instance of GeneratorType"


async def async_generator():
    for i in range(3):
        yield i


@pytest.mark.asyncio
async def test_async_generator_proxy_async_next():
    proxy = AsyncIteratorProxy(async_generator())
    assert proxy.items == []
    assert await proxy.__anext__() == 0
    assert await proxy.__anext__() == 1
    assert await proxy.__anext__() == 2

    with pytest.raises(StopAsyncIteration):
        await proxy.__anext__()

    assert proxy.items == [0, 1, 2]


@pytest.mark.asyncio
async def test_async_generator_proxy_iter():
    original_generator = async_generator()
    proxy = AsyncIteratorProxy(original_generator)

    i = 0
    async for item in proxy:
        assert item == i
        i += 1

    assert proxy.items == [0, 1, 2]


@pytest.mark.asyncio
async def test_async_generator_type():
    """
    Test that AsyncGeneratorProxy is a subclass of AsyncIterator but not AsyncGeneratorType
    """
    proxy = AsyncIteratorProxy(async_generator())
    # AsyncGeneratorProxy is a subclass of AsyncIterator
    assert isinstance(proxy, AsyncIterator), "proxy should be an instance of AsyncIterator"
    # AsyncGeneratorProxy is not a subclass of AsyncGeneratorType
    assert not isinstance(proxy, AsyncGeneratorType), "proxy should not be an instance of AsyncGeneratorType"
