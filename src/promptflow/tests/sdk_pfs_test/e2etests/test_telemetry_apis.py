# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow._sdk._version import VERSION

from ..utils import PFSOperations, check_activity_end_telemetry


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
class TestTelemetryAPIs:
    def test_post_telemetry(self, pfs_op: PFSOperations) -> None:
        from promptflow._sdk._telemetry.activity import generate_request_id

        request_id = generate_request_id()
        user_agent = "prompt-flow-extension/1.8.0 (win32; x64) VS/0.0.1"
        _ = pfs_op.create_telemetry(
            body={
                "eventType": "Start",
                "timestamp": "2021-01-01T00:00:00Z",
                "metadata": {
                    "activityName": "pf.flow.test",
                    "activityType": "InternalCall",
                },
            },
            status_code=200,
            headers={
                "x-ms-promptflow-request-id": request_id,
                "User-Agent": user_agent,
            },
        ).json

        with check_activity_end_telemetry(
            activity_name="pf.flow.test",
            activity_type="InternalCall",
            user_agent=f"{user_agent} local_pfs/{VERSION}",
            request_id=request_id,
        ):
            response = pfs_op.create_telemetry(
                body={
                    "eventType": "End",
                    "timestamp": "2021-01-01T00:00:00Z",
                    "metadata": {
                        "activityName": "pf.flow.test",
                        "activityType": "InternalCall",
                        "completionStatus": "Success",
                        "durationMs": 1000,
                    },
                },
                headers={
                    "x-ms-promptflow-request-id": request_id,
                    "User-Agent": user_agent,
                },
                status_code=200,
            ).json
        assert len(response) >= 1
