import tempfile

import pytest
from pytest_mock import MockerFixture

from promptflow.azure import PFClient
from promptflow.exceptions import UserErrorException


@pytest.mark.unittest
class TestRunOperations:
    def test_download_run_with_invalid_workspace_datastore(self, pf: PFClient, mocker: MockerFixture):
        # test download with invalid workspace datastore
        mocker.patch.object(pf.runs, "_validate_for_run_download")
        mocker.patch.object(pf.runs, "_workspace_default_datastore", "test")
        with tempfile.TemporaryDirectory() as tmp_dir:
            with pytest.raises(UserErrorException, match="workspace default datastore is not supported"):
                pf.runs.download(run="fake_run_name", output=tmp_dir)
