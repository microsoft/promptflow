# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

ENVIRON_TEST_MODE = "PROMPT_FLOW_TEST_MODE"
ENVIRON_TEST_PACKAGE = "PROMPT_FLOW_TEST_PACKAGE"


FILTER_HEADERS = [
    "aml-user-token",
    "authorization",
    "date",
    "etag",
    "request-context",
    "x-aml-cluster",
    "x-ms-access-tier",
    "x-ms-access-tier-inferred",
    "x-ms-client-request-id",
    "x-ms-client-session-id",
    "x-ms-client-user-type",
    "x-ms-correlation-request-id",
    "x-ms-file-permission-key",
    "x-ms-lease-state",
    "x-ms-lease-status",
    "x-ms-server-encrypted",
    "x-ms-ratelimit-remaining-subscription-reads",
    "x-ms-ratelimit-remaining-subscription-writes",
    "x-ms-response-type",
    "x-ms-request-id",
    "x-ms-routing-request-id",
    "x-msedge-ref",
]


class SanitizedValues:
    UUID = "00000000-0000-0000-0000-000000000000"
    SUBSCRIPTION_ID = "00000000-0000-0000-0000-000000000000"
    RESOURCE_GROUP_NAME = "00000"
    WORKSPACE_NAME = "00000"
    WORKSPACE_ID = "00000000-0000-0000-0000-000000000000"
    TENANT_ID = "00000000-0000-0000-0000-000000000000"
    USER_OBJECT_ID = "00000000-0000-0000-0000-000000000000"
    # workspace
    DISCOVERY_URL = "https://eastus.api.azureml.ms/discovery"
    # datastore
    FAKE_KEY = "this is fake key"
    FAKE_ACCOUNT_NAME = "fake_account_name"
    FAKE_CONTAINER_NAME = "fake-container-name"
    FAKE_FILE_SHARE_NAME = "fake-file-share-name"
    # aoai connection
    FAKE_API_BASE = "https://fake.openai.azure.com"
    # storage
    UPLOAD_HASH = "000000000000000000000000000000000000"
    BLOB_STORAGE_REQUEST_HOST = "fake_account_name.blob.core.windows.net"
    FILE_SHARE_REQUEST_HOST = "fake_account_name.file.core.windows.net"
    # PFS
    RUNTIME_NAME = "fake-runtime-name"
    SESSION_ID = "000000000000000000000000000000000000000000000000"
    FLOW_LINEAGE_ID = "0000000000000000000000000000000000000000000000000000000000000000"
    REGION = "fake-region"
    FLOW_ID = "00000000-0000-0000-0000-000000000000"
    COMPUTE_NAME = "fake-compute"
    # trick: "unknown_user" is the value when client fails to get username
    #        use this value so that we don't do extra logic when replay
    USERNAME = "unknown_user"
    # MISC
    EMAIL_USERNAME = "username"
    # run start and end time
    START_TIME = "1717563256142"
    TIMESTAMP = "1717563256242"
    END_TIME = "1717563261483"
    START_UTC = "2000-01-01T00:00:00.000000Z"
    END_UTC = "2000-01-02T00:00:00.000000Z"
    # Promptflow RunID
    RUN_ID = "evals_e2etests_run_id_xxx0_xxx_00000000_000000_000000"
    RUN_UUID = "00000000-0000-0000-0000-000000000000"
    EXP_UUID = "11111111-1111-1111-1111-111111111111"
    # Files, created by the promptflow
    ROOT_PF_PATH = f"promptflow/PromptFlowArtifacts/{RUN_ID}"
    EXEC_LOGS = f"{ROOT_PF_PATH}/logs/azureml/executionlogs.txt"
    FLOW_DEF = f"{ROOT_PF_PATH}/flow.flex.yaml"
    CONTAINER = f"dcid.{RUN_ID}"
    ARTIFACT_ID = f"ExperimentRun/dcid.{CONTAINER}/instance_results.jsonl"
    # Coverage file is only created during pytest run with coverage enabled.
    COVERAGE = ".coverage.sanitized-suffix.00000.xxxxxxxx"
    DATA_PATH = {
        "dataStoreName": "workspaceblobstore",
        "relativePath": f"{ROOT_PF_PATH}/instance_results.jsonl",
    }
    OUTPUTS = {
        "debug_info": {"assetId": f"azureml://locations/{RUN_ID}_output_data_debug_info/versions/1",
                       "type": "UriFolder"},
        "flow_outputs": {"assetId": f"azureml://locations/{RUN_ID}_output_data_flow_outputs/versions/1",
                         "type": "UriFolder"}
    }

    # Fake Application insights event
    FAKE_APP_INSIGHTS = [
        {
            "ver": 1,
            "name": "Microsoft.ApplicationInsights.Event",
            "time": "2024-06-06T23:20:59.838896Z",
            "sampleRate": 100.0,
            "iKey": UUID,
            "tags": {"foo": "bar"},
        }
    ]


class AzureMLResourceTypes:
    CONNECTION = "Microsoft.MachineLearningServices/workspaces/connections"
    DATASTORE = "Microsoft.MachineLearningServices/workspaces/datastores"
    WORKSPACE = "Microsoft.MachineLearningServices/workspaces"


TEST_CLASSES_FOR_RUN_INTEGRATION_TEST_RECORDING = [
    "TestCliWithAzure",
    "TestFlowRun",
    "TestFlow",
    "TestTelemetry",
    "TestAzureCliPerf",
    "TestCSharpSdk",
    "TestMetricsUpload",
]
