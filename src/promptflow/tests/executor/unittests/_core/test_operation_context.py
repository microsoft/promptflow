import threading

import pytest

from promptflow import PFClient
from promptflow._core.operation_context import OperationContext
from promptflow._version import VERSION
from promptflow.contracts.run_mode import RunMode
from promptflow._sdk._user_agent import USER_AGENT as SDK_USER_AGENT


def set_run_mode(context: OperationContext, run_mode: RunMode):
    """This method simulates the runtime.execute_request()

    It is aimed to set the run_mode into operation context.
    """
    context.run_mode = run_mode.name if run_mode is not None else ""


@pytest.mark.unittest
class TestOperationContext:
    def test_get_user_agent(self):
        operation_context = OperationContext()
        assert operation_context.get_user_agent() == f"promptflow/{VERSION}"

        operation_context.user_agent = "test_agent/0.0.2"
        assert operation_context.get_user_agent() == f"promptflow/{VERSION} test_agent/0.0.2"

    @pytest.mark.parametrize(
        "run_mode, expected",
        [
            (RunMode.Test, "Test"),
            (RunMode.SingleNode, "SingleNode"),
            (RunMode.Batch, "Batch"),
        ],
    )
    def test_run_mode(self, run_mode, expected):
        context = OperationContext()
        set_run_mode(context, run_mode)
        assert context.run_mode == expected

    def test_context_dict(self):
        context = OperationContext()

        context.run_mode = "Flow"
        context.user_agent = "test_agent/0.0.2"
        context.none_value = None

        context_dict = context.get_context_dict()

        assert context_dict["run_mode"] == "Flow"
        assert context_dict["user_agent"] == "test_agent/0.0.2"
        assert context_dict["none_value"] is None

    def test_setattr(self):
        context = OperationContext()

        context.run_mode = "Flow"
        assert context["run_mode"] == "Flow"

    def test_setattr_non_primitive(self):
        # Test set non-primitive type
        context = OperationContext()

        with pytest.raises(TypeError):
            context.foo = [1, 2, 3]

    def test_getattr(self):
        context = OperationContext()

        context["run_mode"] = "Flow"
        assert context.run_mode == "Flow"

    def test_getattr_missing(self):
        context = OperationContext()

        with pytest.raises(AttributeError):
            context.foo

    def test_delattr(self):
        # test that delattr works as expected
        context = OperationContext()
        context.foo = "bar"
        del context.foo
        assert "foo" not in context

        # test that delattr raises AttributeError for non-existent name
        with pytest.raises(AttributeError):
            del context.baz

    def test_append_user_agent(self):
        context = OperationContext()
        user_agent = ' ' + context.user_agent if 'user_agent' in context else ''

        context.append_user_agent("test_agent/0.0.2")
        assert context.user_agent == "test_agent/0.0.2" + user_agent

        context.append_user_agent("test_agent/0.0.3")
        assert context.user_agent == "test_agent/0.0.2 test_agent/0.0.3" + user_agent

    def test_get_instance(self):
        context1 = OperationContext.get_instance()
        context2 = OperationContext.get_instance()
        assert context1 is context2

    def test_set_batch_input_source_from_inputs_mapping_run(self):
        input_mapping = {"input1": "${run.outputs.output1}", "input2": "${run.outputs.output2}"}
        context = OperationContext()
        context.set_batch_input_source_from_inputs_mapping(input_mapping)
        assert context.batch_input_source == "Run"

    def test_set_batch_input_source_from_inputs_mapping_data(self):
        input_mapping = {"url": "${data.url}"}
        context = OperationContext()
        context.set_batch_input_source_from_inputs_mapping(input_mapping)
        assert context.batch_input_source == "Data"

    def test_set_batch_input_source_from_inputs_mapping_none(self):
        input_mapping = None
        context = OperationContext()
        assert not hasattr(context, "batch_input_source")
        context.set_batch_input_source_from_inputs_mapping(input_mapping)
        assert context.batch_input_source == "Data"

    def test_set_batch_input_source_from_inputs_mapping_empty(self):
        input_mapping = {}
        context = OperationContext()
        assert not hasattr(context, "batch_input_source")
        context.set_batch_input_source_from_inputs_mapping(input_mapping)
        assert context.batch_input_source == "Data"

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

    def test_duplicate_ua(self):
        context = OperationContext.get_instance()
        default_ua = context.get('user_agent', '')

        try:
            ua1 = 'ua1 ua2 ua3'
            # context['user_agent'] = ua1,
            # Due to concurrent running of tests, this assignment will cause overwrite of promptflow-sdk/0.0.1,
            # resulting in test failure
            context.append_user_agent(ua1)  # Add fixed UA
            origin_agent = context.get_user_agent()

            ua2 = '    ua3   ua2  ua1'
            context.append_user_agent(ua2)  # Env configuration ua with extra spaces, duplicate ua.
            agent = context.get_user_agent()
            assert agent == (origin_agent + ' ' + ua2).strip()

            ua3 = '  ua3   ua2 ua1  ua4  '
            context.append_user_agent(ua3)  # Env modifies ua with extra spaces, duplicate ua except ua4.
            agent = context.get_user_agent()
            assert agent == (origin_agent + ' ' + ua2 + ' ' + ua3).strip()

            ua4 = 'ua1 ua2'  #
            context.append_user_agent(ua4)  # Env modifies ua with extra spaces, duplicate ua but not be added.
            agent = context.get_user_agent()
            assert agent == (origin_agent + ' ' + ua2 + ' ' + ua3).strip()

            ua5 = 'ua2 ua4 ua5    '
            context.append_user_agent(ua5)  # Env modifies ua with extra spaces, duplicate ua except ua5.
            agent = context.get_user_agent()
            assert agent == (origin_agent + ' ' + ua2 + ' ' + ua3 + ' ' + ua5).strip()
        except Exception as e:
            raise e
        finally:
            context['user_agent'] = default_ua

    def test_extra_spaces_ua(self):
        context = OperationContext.get_instance()
        default_ua = context.get('user_agent', '')

        try:
            origin_agent = context.get_user_agent()
            ua1 = '    ua1   ua2   ua3    '
            context.append_user_agent(ua1)
            # context['user_agent'] = ua1,
            # Due to concurrent running of tests, this assignment will cause overwrite of promptflow-sdk/0.0.1,
            # resulting in test failure
            assert context.get_user_agent() == (origin_agent + ' ' + ua1).strip()

            ua2 = 'ua4      ua5      ua6      '
            context.append_user_agent(ua2)
            assert context.get_user_agent() == (origin_agent + ' ' + ua1 + ' ' + ua2).strip()
        except Exception as e:
            raise e
        finally:
            context['user_agent'] = default_ua

    def test_ua_covered(self):
        context = OperationContext.get_instance()
        default_ua = context.get('user_agent', '')
        try:
            PFClient()
            assert SDK_USER_AGENT in context.get_user_agent()

            context["user_agent"] = 'test_agent'
            assert SDK_USER_AGENT not in context.get_user_agent()
        except Exception as e:
            raise e
        finally:
            context['user_agent'] = default_ua
