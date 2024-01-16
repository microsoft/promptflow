# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from ..utils import PFSOperations, check_activity_end_telemetry


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
class TestTelemetryAPIs:
    def test_post_telemetry(self, pfs_op: PFSOperations) -> None:
        response = pfs_op.create_telemetry(
            body={
                "eventType": "Start",
                "timestamp": "2021-01-01T00:00:00Z",
                "metadata": {
                    "activityName": "pf.flow.test",
                    "activityType": "InternalCall",
                },
            },
            status_code=200,
        ).json

        with check_activity_end_telemetry(
            activity_name="pf.flow.test",
            activity_type="InternalCall",
            # TODO: not sure how to set user_agent in request
            user_agent="local_pfs/0.0.1",
        ):
            response = pfs_op.create_telemetry(
                body={
                    "eventType": "End",
                    "timestamp": "2021-01-01T00:00:00Z",
                    "metadata": {
                        "requestId": response["requestId"],
                        "activityName": "pf.flow.test",
                        "activityType": "InternalCall",
                        "completionStatus": "Success",
                        "durationMs": 1000,
                    },
                },
                status_code=200,
            ).json
        assert len(response) >= 1
