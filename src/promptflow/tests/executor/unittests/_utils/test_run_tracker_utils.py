import pytest

from promptflow._utils.run_tracker_utils import _deep_copy_and_extract_items_from_generator_proxy
from promptflow.tracing.contracts.iterator_proxy import IteratorProxy


@pytest.mark.unittest
class TestDeepCopyAndExtract:
    def test_deep_copy_simple_value(self):
        value = 10
        result = _deep_copy_and_extract_items_from_generator_proxy(value)
        assert value == result

    def test_deep_copy_list(self):
        value = [1, 2, 3]
        result = _deep_copy_and_extract_items_from_generator_proxy(value)
        assert value == result
        assert id(value) != id(result), "List should be deep copied"

    def test_deep_copy_dict(self):
        value = {"a": 1, "b": 2}
        result = _deep_copy_and_extract_items_from_generator_proxy(value)
        assert value == result
        assert id(value) != id(result), "Dict should be deep copied"

    def test_extract_generator_proxy_items(self):
        generator_proxy_value = IteratorProxy(None)
        generator_proxy_value._items = [1, 2]
        expected = [1, 2]
        result = _deep_copy_and_extract_items_from_generator_proxy(generator_proxy_value)
        assert expected == result

    def test_composite(self):
        value = {"a": [1, 2, 3], "b": IteratorProxy(None)}
        value["b"]._items = [1, 2]
        expected = {"a": [1, 2, 3], "b": [1, 2]}
        result = _deep_copy_and_extract_items_from_generator_proxy(value)
        assert expected == result
