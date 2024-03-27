import threading

import pytest

from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._version import VERSION


def run_test_with_new_context(assert_func):
    context = OperationContext.get_instance()
    assert_func(context)
    context.set_instance(None)


@pytest.mark.unittest
class TestOperationContext:
    def test_copy_and_set_instance(self):
        def assert_context(context):
            original_context = context
            original_context._add_otel_attributes("test_key", "test_value")
            context_copy = original_context.copy()
            OperationContext.set_instance(context_copy)
            context = OperationContext.get_instance()
            context._add_otel_attributes("test_key2", "test_value2")
            assert context._get_otel_attributes() == {"test_key": "test_value", "test_key2": "test_value2"}
            assert original_context._get_otel_attributes() == {"test_key": "test_value"}

        run_test_with_new_context(assert_context)

    def test_user_agent(self):
        def assert_context(context):
            context.append_user_agent("test_agent/0.0.1")
            context.append_user_agent("test_agent/0.0.2")
            assert context.get_user_agent() == f"test_agent/0.0.1 test_agent/0.0.2 promptflow-tracing/{VERSION}"

        run_test_with_new_context(assert_context)

    def test_get_request_id(self):
        def assert_context(context):
            assert context.get_request_id() == "unknown"
            context["request_id"] = "test_request_id"
            assert context.get_request_id() == "test_request_id"

        run_test_with_new_context(assert_context)

    def test_context_dict(self):
        def assert_context(context):
            context.test_key = "test_value"
            context.test_key2 = "test_value2"
            context_dict = context.get_context_dict()
            assert context_dict["test_key"] == "test_value"
            assert context_dict["test_key2"] == "test_value2"
        run_test_with_new_context(assert_context)

    def test_setattr(self):
        def assert_context(context):
            # 1. Normal case
            context.test_key = "test_value"
            assert context["test_key"] == "test_value"
            # 2. Non-primitive type value
            context.test_key = [1, 2, 3]
            assert context["test_key"] == [1, 2, 3]
        run_test_with_new_context(assert_context)

    def test_getattr(self):
        def assert_context(context):
            # 1. Normal case
            context["test_key"] = "test_value"
            assert context.test_key == "test_value"
            # 2. Non-existent key
            with pytest.raises(AttributeError):
                context.non_exist_key
        run_test_with_new_context(assert_context)

    def test_delattr(self):
        def assert_context(context):
            # 1. Normal case
            context.test_key = "test_value"
            del context.test_key
            assert "test_key" not in context
            # 2. Non-existent key
            with pytest.raises(AttributeError):
                del context.non_exist_key
        run_test_with_new_context(assert_context)

    def test_default_tracing_keys(self):
        def assert_context(context):
            context.set_default_tracing_keys({"test_key", "test_key2"})
            assert context._tracking_keys == {"test_key", "test_key2"}
            context.set_default_tracing_keys({"test_key3"})
            assert context._tracking_keys == {"test_key", "test_key2", "test_key3"}
        run_test_with_new_context(assert_context)

    def test_get_instance(self):
        context1 = OperationContext.get_instance()
        context2 = OperationContext.get_instance()
        assert context1 is context2

    def test_different_thread_have_different_instance(self):
        # create a list to store the OperationContext instances from each thread
        instances = []

        # define a function that gets the OperationContext instance and appends it to the list
        def get_instance():
            instance = OperationContext.get_instance()
            instances.append(instance)

        # create two threads and run the function in each thread
        thread1 = threading.Thread(target=get_instance)
        thread2 = threading.Thread(target=get_instance)
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # assert that the list has two elements and they are different objects
        assert len(instances) == 2
        assert instances[0] is not instances[1]
