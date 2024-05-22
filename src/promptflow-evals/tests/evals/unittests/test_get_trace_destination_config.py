import pytest
from unittest.mock import patch
from promptflow.evals.evaluate._utils import _get_trace_destination_config


@pytest.fixture
def patch_config_validation():
    with patch("promptflow._sdk._configuration.Configuration._validate", return_value=None):
        yield


@pytest.mark.unittest
class TestGetTraceDestinationConfig:
    @pytest.mark.parametrize("trace_destination, expected_trace_destination",
                             [
                                 ("None", None),
                                 ("none", None),
                                 ("NONE", None),
                                 ("NoNe", None),
                             ])
    def test_get_trace_destination_config(self, trace_destination, expected_trace_destination):
        with patch("promptflow._sdk._configuration.Configuration.get_trace_destination",
                   return_value=trace_destination):
            assert _get_trace_destination_config(None) == expected_trace_destination

    def test_get_trace_destination_config_with_override(self, patch_config_validation):
        trace_destination = ("azureml://subscriptions/subscription-id/resourceGroups/resource-group-name/providers"
                             "/Microsoft.MachineLearningServices/workspaces/test_get_trace_destination_config")
        global_trace_destination_value = _get_trace_destination_config(None)
        overidden_trace_destination_value = _get_trace_destination_config(trace_destination)
        assert global_trace_destination_value != overidden_trace_destination_value
        assert overidden_trace_destination_value == trace_destination
