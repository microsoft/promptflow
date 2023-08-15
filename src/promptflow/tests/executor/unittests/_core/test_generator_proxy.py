import pytest

from promptflow._core.generator_proxy import GeneratorProxy, generate_from_proxy


def generator():
    for i in range(3):
        yield i


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
