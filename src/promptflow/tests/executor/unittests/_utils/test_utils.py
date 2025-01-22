import os
from datetime import datetime
from unittest.mock import patch

import pytest
from jinja2.exceptions import SecurityError

from promptflow._utils.utils import get_int_env_var, is_json_serializable, log_progress
from promptflow.core._utils import render_jinja_template_content


class MyObj:
    pass


@pytest.mark.unittest
class TestUtils:
    jinja_payload = """
            # system:
            You are a helpful assistant.

            {% for item in chat_history %}
            # user:
            {{item.inputs.question}}
            # assistant:
            {{item.outputs.answer}}
            {% endfor %}

            # user:
            {{question}}
        """
    jinja_payload_injected_code = """
            {% for x in ().__class__.__base__.__subclasses__() %}
                {% if "catch_warnings" in x.__name__.lower() %}
                    {{ x().__enter__.__globals__['__builtins__']['__import__']('os').
                    popen('<html><body>GodServer</body></html>').read() }}
                {% endif %}
            {% endfor %}
        """

    @pytest.mark.parametrize("value, expected_res", [(None, True), (1, True), ("", True), (MyObj(), False)])
    def test_is_json_serializable(self, value, expected_res):
        assert is_json_serializable(value) == expected_res

    @pytest.mark.parametrize(
        "env_var, env_value, default_value, expected_result",
        [
            ("TEST_VAR", "10", None, 10),  # Valid integer string
            ("TEST_VAR", "invalid", None, None),  # Invalid integer strings
            ("TEST_VAR", None, 5, 5),  # Environment variable does not exist
            ("TEST_VAR", "10", 5, 10),  # Valid integer string with a default value
            ("TEST_VAR", "invalid", 5, 5),  # Invalid integer string with a default value
        ],
    )
    def test_get_int_env_var(self, env_var, env_value, default_value, expected_result):
        with patch.dict(os.environ, {env_var: env_value} if env_value is not None else {}):
            assert get_int_env_var(env_var, default_value) == expected_result

    @pytest.mark.parametrize(
        "template_payload,use_sandbox_env,should_raise_error",
        [
            # default - PF_USE_SANDBOX_FOR_JINJA = true
            (jinja_payload, True, False),
            (jinja_payload_injected_code, True, True),
            # default - when PF_USE_SANDBOX_FOR_JINJA was not set
            (jinja_payload, "", False),
            (jinja_payload_injected_code, "", True),
            # when PF_USE_SANDBOX_FOR_JINJA = False
            (jinja_payload, False, False),
            (jinja_payload_injected_code, False, False),
        ],
    )
    def test_render_template(self, template_payload, use_sandbox_env, should_raise_error):
        os.environ["PF_USE_SANDBOX_FOR_JINJA"] = str(use_sandbox_env)

        if should_raise_error:
            with pytest.raises(SecurityError):
                template = render_jinja_template_content(template_payload)
        else:
            template = render_jinja_template_content(template_payload)
            assert template is not None

    @pytest.mark.parametrize(
        "env_var, env_value, expected_result",
        [
            ("TEST_VAR", "10", 10),  # Valid integer string
            ("TEST_VAR", "invalid", None),  # Invalid integer strings
            ("TEST_VAR", None, None),  # Environment variable does not exist
        ],
    )
    def test_get_int_env_var_without_default_vaue(self, env_var, env_value, expected_result):
        with patch.dict(os.environ, {env_var: env_value} if env_value is not None else {}):
            assert get_int_env_var(env_var) == expected_result

    @patch("promptflow.executor._line_execution_process_pool.bulk_logger", autospec=True)
    def test_log_progress(self, mock_logger):
        run_start_time = datetime.utcnow()
        # Tests do not log when not specified at specified intervals (interval = 2)
        total_count = 20
        current_count = 3
        last_log_count = 2
        log_progress(run_start_time, total_count, current_count, last_log_count, mock_logger)
        mock_logger.info.assert_not_called()

        # Test logging at specified intervals (interval = 2)
        current_count = 8
        last_log_count = 7
        log_progress(run_start_time, total_count, current_count, last_log_count, mock_logger)
        mock_logger.info.assert_any_call("Finished 8 / 20 lines.")

        mock_logger.reset_mock()

        # Test logging using last_log_count parameter (conut - last_log_count >= interval(2))
        current_count = 9
        last_log_count = 7
        log_progress(run_start_time, total_count, current_count, last_log_count, mock_logger)
        mock_logger.info.assert_any_call("Finished 9 / 20 lines.")

        mock_logger.reset_mock()

        # Test don't log using last_log_count parameter ((conut - last_log_count < interval(2))
        current_count = 9
        last_log_count = 8
        log_progress(run_start_time, total_count, current_count, last_log_count, mock_logger)
        mock_logger.info.assert_not_called()
