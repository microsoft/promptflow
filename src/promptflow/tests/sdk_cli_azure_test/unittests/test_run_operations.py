from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from promptflow.azure import PFClient
from promptflow.exceptions import UserErrorException


@pytest.mark.unittest
class TestRunOperations:
    def test_download_run_with_invalid_workspace_datastore(self, pf: PFClient):
        # test download with invalid workspace datastore
        with (
            TemporaryDirectory() as tmp_dir,
            patch.object(pf.runs, "_validate_for_run_download"),
            patch.object(pf.runs, "_workspace_default_datastore", "test"),
        ):
            with pytest.raises(UserErrorException, match="workspace default datastore is not supported"):
                pf.runs.download(run="fake_run_name", output=tmp_dir)
