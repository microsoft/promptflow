from unittest.mock import Mock

import pytest

from promptflow.tracing._span_wrapper import SpanWrapper


class SimpleObject:
    foo = "bar"


def test_init():
    mock_span = Mock()
    wrapper = SpanWrapper(mock_span)
    assert wrapper.__wrapped__ is mock_span


def test_getattr():
    simple_obj = SimpleObject()
    wrapper = SpanWrapper(simple_obj)
    assert wrapper.foo == "bar"
    with pytest.raises(AttributeError):
        wrapper.non_existent_attr


def test_setattr():
    mock_span = Mock()
    wrapper = SpanWrapper(mock_span)
    wrapper._self_foo = "bar"
    assert wrapper._self_foo == "bar"
    wrapper.foo = "baz"
    assert mock_span.foo == "baz"


def test_should_end():
    mock_span = Mock()
    wrapper = SpanWrapper(mock_span)
    assert wrapper.should_end is True
    wrapper.should_end = False
    assert wrapper.should_end is False
    with pytest.raises(ValueError):
        wrapper.should_end = "not a boolean"


def test_class():
    mock_span = SimpleObject()
    wrapper = SpanWrapper(mock_span)
    assert wrapper.__class__ is mock_span.__class__

    isinstance(wrapper, SpanWrapper)
    isinstance(wrapper, SimpleObject)
