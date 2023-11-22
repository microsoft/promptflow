import pytest

from promptflow._sdk._errors import RunOperationParameterError
from promptflow.azure import PFClient


@pytest.mark.unittest
class TestPFClientAzure:
    def test_wrong_client_parameters(self):
        # test wrong client parameters
        with pytest.raises(RunOperationParameterError, match="You have passed in the wrong parameter name"):
            PFClient(
                subscription_id="fake_subscription_id",
                resource_group="fake_resource_group",
                workspace_name="fake_workspace_name",
            )
