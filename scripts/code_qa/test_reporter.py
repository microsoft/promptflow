import os
import platform
import pytest

from unittest.mock import patch, MagicMock

import report_to_app_insights
import tempfile


class TestReporter:
    """The set of local tests to test reporting to application insights."""

    @pytest.mark.parametrize(
        'value,expected_val',
        [
            (42, {'value': 42.}),
            ('{"foo": 1, "bar": 2}', {"foo": 1, "bar": 2})
        ]
    )
    def test_logging_value(self, value, expected_val):
        """Test loading values from."""
        mock_logger = MagicMock()
        expected = {
            "activity_name": 'test_act',
            "activity_type": "ci_cd_analytics",
            "OS": platform.system(),
            "OS_release": platform.release(),
            "branch": "some_branch",
            "git_hub_action_run_id": "gh_run_id",
            "git_hub_workflow": "gh_wf"
        }
        expected.update(expected_val)
        with patch('report_to_app_insights.get_telemetry_logger', return_value=mock_logger):
            report_to_app_insights.main(
                'test_act', value, "gh_run_id", "gh_wf", 'my_action', "some_branch", junit_file=None)
        mock_logger.info.assert_called_with('my_action', extra={'custom_dimensions': expected})

    def test_log_junit_xml(self):
        """Test that we are loading junit xml files as expected."""
        content = (
            '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">'
            '<testcase classname="MyTestClass1" name="my_successful_test_method" time="4.2"/>'
            '<testcase classname="MyTestClass2" name="my_unsuccessful_test_method" time="4.2">'
            '<failure message="Everything failed">fail :(</failure></testcase>'
            '</testsuite></testsuites>'
        )
        mock_logger = MagicMock()
        expected = {
            "activity_name": 'test_act',
            "activity_type": "ci_cd_analytics",
            "OS": platform.system(),
            "OS_release": platform.release(),
            "MyTestClass1::my_successful_test_method": 4.2,
            "branch": "some_branch",
            "git_hub_action_run_id": "gh_run_id",
            "git_hub_workflow": "gh_wf"
        }
        with tempfile.TemporaryDirectory() as d:
            file_xml = os.path.join(d, "test-results.xml")
            with open(file_xml, 'w') as f:
                f.write(content)
            with patch('report_to_app_insights.get_telemetry_logger', return_value=mock_logger):
                report_to_app_insights.main(
                    'test_act', -1, "gh_run_id", "gh_wf", 'my_action', "some_branch", junit_file=file_xml)

        mock_logger.info.assert_called_with('my_action', extra={'custom_dimensions': expected})
