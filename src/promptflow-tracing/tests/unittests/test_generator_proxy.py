from types import AsyncGeneratorType, GeneratorType
from typing import AsyncIterator, Iterator

import pytest

from promptflow.tracing.contracts.generator_proxy import (
    AsyncGeneratorProxy,
    GeneratorProxy,
    generate_from_async_proxy,
    generate_from_proxy,
)


def generator():
    for i in range(3):
        yield i


def iterator():
    return iter([0, 1, 2])


@pytest.mark.unittest
def test_generator_proxy_next():
    proxy = GeneratorProxy(generator())
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
    proxy = GeneratorProxy(generator())

    for num in proxy:
        assert num == next(original_generator)

    assert proxy.items == [0, 1, 2]


@pytest.mark.unittest
def test_generate_from_proxy():
    proxy = GeneratorProxy(generator())
    original_generator = generator()

    for i in generate_from_proxy(proxy):
        assert i == next(original_generator)

    assert proxy.items == [0, 1, 2]


@pytest.mark.unittest
def test_iterator_proxy_next():
    proxy = GeneratorProxy(iterator())
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
    proxy = GeneratorProxy(iterator())

    for num in proxy:
        assert num == next(original_iterator)

    assert proxy.items == [0, 1, 2]


@pytest.mark.unittest
def test_generate_from_iterator_proxy():
    proxy = GeneratorProxy(iterator())
    original_iterator = iterator()

    for i in generate_from_proxy(proxy):
        assert i == next(original_iterator)

    assert proxy.items == [0, 1, 2]


@pytest.mark.unittest
def test_generator_proxy_type():
    """
    Test that GeneratorProxy is a subclass of Iterator but not GeneratorType,
    and that generate_from_proxy returns a GeneratorType.
    """
    proxy = GeneratorProxy(generator())
    # GeneratorProxy is a subclass of Iterator
    assert isinstance(proxy, Iterator), "proxy should be an instance of Iterator"
    # GeneratorProxy is not a subclass of GeneratorType
    assert not isinstance(proxy, GeneratorType), "proxy should not be an instance of GeneratorType"
    # generate_from_proxy returns a GeneratorType
    assert isinstance(
        generate_from_proxy(proxy), GeneratorType
    ), "generate_from_proxy should return an instance of GeneratorType"


async def async_generator():
    for i in range(3):
        yield i


@pytest.mark.asyncio
async def test_async_generator_proxy_async_next():
    proxy = AsyncGeneratorProxy(async_generator())
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
    proxy = AsyncGeneratorProxy(original_generator)

    i = 0
    async for item in proxy:
        assert item == i
        i += 1

    assert proxy.items == [0, 1, 2]


@pytest.mark.asyncio
async def test_generate_from_async_proxy():
    proxy = AsyncGeneratorProxy(async_generator())

    i = 0
    async for item in generate_from_async_proxy(proxy):
        assert item == i
        i += 1

    assert proxy.items == [0, 1, 2]


@pytest.mark.asyncio
async def test_async_generator_type():
    """
    Test that AsyncGeneratorProxy is a subclass of AsyncIterator but not AsyncGeneratorType,
    and that generate_from_async_proxy returns an AsyncGeneratorType.
    """
    proxy = AsyncGeneratorProxy(async_generator())
    # AsyncGeneratorProxy is a subclass of AsyncIterator
    assert isinstance(proxy, AsyncIterator), "proxy should be an instance of AsyncIterator"
    # AsyncGeneratorProxy is not a subclass of AsyncGeneratorType
    assert not isinstance(proxy, AsyncGeneratorType), "proxy should not be an instance of AsyncGeneratorType"
    # generate_from_async_proxy returns an AsyncGeneratorType
    assert isinstance(
        generate_from_async_proxy(proxy), AsyncGeneratorType
    ), "generate_from_async_proxy should return an instance of AsyncGeneratorType"
