import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from azure.ai.ml import ManagedIdentityConfiguration
from azure.ai.ml.entities import IdentityConfiguration
from pytest_mock import MockerFixture
from sdk_cli_azure_test.conftest import DATAS_DIR, EAGER_FLOWS_DIR, FLOWS_DIR

from promptflow._sdk._errors import RunOperationParameterError, UploadUserError, UserAuthenticationError
from promptflow._sdk._utilities.tracing_utils import _parse_otel_span_status_code
from promptflow._sdk.entities import Run
from promptflow._sdk.operations._run_operations import RunOperations
from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow.azure import PFClient
from promptflow.azure.operations._async_run_uploader import AsyncRunUploader
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

    def test_run_with_identity(self, pf: PFClient, mocker: MockerFixture):
        mock_workspace = MagicMock()
        mock_workspace.identity = IdentityConfiguration(
            type="managed",
            user_assigned_identities=[
                ManagedIdentityConfiguration(client_id="fake_client_id", resource_id="fake_resource_id")
            ],
        )
        mocker.patch.object(pf.runs, "_workspace", mock_workspace)
        run = Run(
            flow=f"{FLOWS_DIR}/print_env_var",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            name="test_run",
            identity={"type": "managed", "client_id": "fake_client_id"},
        )
        pf.runs._resolve_identity(run)
        rest_run = run._to_rest_object()
        assert rest_run.identity == "fake_resource_id"

        mock_workspace = MagicMock()
        mock_workspace.primary_user_assigned_identity = "fake_primary_user_assigned_identity"
        mocker.patch.object(pf.runs, "_workspace", mock_workspace)
        run = Run(
            flow=f"{FLOWS_DIR}/print_env_var",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            name="test_run",
            identity={"type": "managed"},
        )
        pf.runs._resolve_identity(run)
        rest_run = run._to_rest_object()
        assert rest_run.identity == "fake_primary_user_assigned_identity"

    @pytest.mark.parametrize(
        "identity, error_msg",
        [
            # no primary_user_assigned_identity
            ({"type": "managed"}, "Primary user assigned identity not found in workspace"),
            # no user_assigned_identities
            ({"type": "managed", "client_id": "xxx"}, "Failed to get identities with id"),
            # unsupported type
            ({"type": "managed_identity"}, "is not supported"),
        ],
    )
    def test_run_with_identity_illegal_cases(self, pf: PFClient, identity, error_msg):
        mock_workspace = MagicMock(primary_user_assigned_identity=None)
        with patch.object(pf.runs, "_workspace", mock_workspace):
            run = Run(
                flow=f"{FLOWS_DIR}/print_env_var",
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                name="test_run",
                identity=identity,
            )
            with pytest.raises(UserErrorException) as e:
                pf.runs._resolve_identity(run)
            assert error_msg in str(e)

    def test_flex_flow_with_imported_func(self, pf: PFClient):
        # TODO(3017093): won't support this for now
        with pytest.raises(UserErrorException) as e:
            pf.run(
                flow=_parse_otel_span_status_code,
                data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
                # set code folder to avoid snapshot too big
                code=f"{EAGER_FLOWS_DIR}/multiple_entries",
                column_mapping={"value": "${data.input_val}"},
            )
        assert "not supported" in str(e)

    def test_wrong_workspace_type(
        self, mocker: MockerFixture, subscription_id: str, resource_group_name: str, workspace_name: str
    ):
        from sdk_cli_azure_test._azure_utils import get_cred

        from promptflow.recording.azure import get_pf_client_for_replay

        # the test target "_workspace_default_datastore" is a cached property so the pf client needs to be recreated
        # otherwise the test may fail due to the cached value
        if pytest.is_replay:
            pf = get_pf_client_for_replay()
        else:
            pf = PFClient(
                credential=get_cred(),
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
            )
        # test wrong workspace type "hub"
        mocker.patch.object(pf.runs._workspace, "_kind", "hub")
        with pytest.raises(RunOperationParameterError, match="Failed to get default workspace datastore"):
            datastore = pf.runs._workspace_default_datastore
            assert datastore

    @pytest.mark.usefixtures("mock_isinstance_for_mock_datastore")
    def test_upload_run_with_invalid_workspace_datastore(self, pf: PFClient, mocker: MockerFixture):
        # test download with invalid workspace datastore
        from promptflow._sdk.operations import RunOperations

        mocked = mocker.patch.object(RunOperations, "get")
        mocked.return_value.run = None
        mocked.return_value.status = "Completed"
        mocker.patch.object(pf.runs, "_workspace_default_datastore", "test")
        with pytest.raises(UserErrorException, match="workspace default datastore is not supported"):
            pf.runs._upload(run="fake_run_name")

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Subscription not found.")
    @pytest.mark.usefixtures("mock_isinstance_for_mock_datastore")
    def test_upload_run_with_running_status(self, pf: PFClient):
        # test upload run with running status
        with patch.object(RunOperations, "get") as mock_get:
            mock_get.return_value.status = "Running"
            with pytest.raises(UserErrorException, match="Can only upload the run with status"):
                pf.runs._upload(run="fake_run_name")

    @pytest.mark.usefixtures("mock_isinstance_for_mock_datastore")
    def test_upload_run_with_authentication_error(self, pf: PFClient, mocker: MockerFixture):
        # test upload run with authentication error
        from azure.core.exceptions import HttpResponseError

        random_data = Path(DATAS_DIR, "numbers.jsonl")
        response = MagicMock()
        response.status_code = 403
        blob_client = MagicMock()
        blob_client.upload_blob.side_effect = HttpResponseError(response=response)

        mocker.patch.object(AsyncRunUploader, "_get_datastore_with_secrets")
        run_uploader = AsyncRunUploader._from_run_operations(run_ops=pf.runs)
        run_uploader._set_run(MagicMock())
        with pytest.raises(UserAuthenticationError, match="User does not have permission"):
            async_run_allowing_running_loop(run_uploader._upload_single_blob, blob_client, random_data)

    @pytest.mark.usefixtures("mock_isinstance_for_mock_datastore")
    def test_upload_run_with_run_exist(
        self,
        pf: PFClient,
        mocker: MockerFixture,
    ):
        # test upload run with run exist
        mocker.patch.object(AsyncRunUploader, "_get_datastore_with_secrets")
        mocker.patch.object(pf.runs, "get")
        run_uploader = AsyncRunUploader._from_run_operations(run_ops=pf.runs)
        mocker.patch.object(run_uploader, "overwrite", False)

        with pytest.raises(UploadUserError, match="cannot upload the run record"):
            run_uploader._check_run_exists(run=MagicMock())
