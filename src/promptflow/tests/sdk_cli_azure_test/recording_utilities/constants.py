# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

TEST_RUN_LIVE = "PROMPT_FLOW_TEST_RUN_LIVE"
SKIP_LIVE_RECORDING = "PROMPT_FLOW_SKIP_LIVE_RECORDING"

FILTER_HEADERS = [
    "aml-user-token",
    "authorization",
    "content-md5",
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
    "x-ms-lease-state",
    "x-ms-lease-status",
    "x-ms-meta-name",
    "x-ms-meta-upload_status",
    "x-ms-meta-version",
    "x-ms-server-encrypted",
    "x-ms-ratelimit-remaining-subscription-reads",
    "x-ms-ratelimit-remaining-subscription-writes",
    "x-ms-response-type",
    "x-ms-request-id",
    "x-ms-routing-request-id",
    "x-msedge-ref",
]


class SanitizedValues:
    SUBSCRIPTION_ID = "00000000-0000-0000-0000-000000000000"
    RESOURCE_GROUP_NAME = "00000"
    WORKSPACE_NAME = "00000"
    # datastore
    FAKE_KEY = "this is fake key"
    FAKE_ACCOUNT_NAME = "fake_account_name"
    FAKE_CONTAINER_NAME = "fake-container-name"
    # aoai connection
    FAKE_API_BASE = "https://fake.openai.azure.com"
    # storage
    UPLOAD_HASH = "000000000000000000000000000000000000"


class AzureMLResourceTypes:
    CONNECTION = "Microsoft.MachineLearningServices/workspaces/connections"
    DATASTORE = "Microsoft.MachineLearningServices/workspaces/datastores"
    WORKSPACE = "Microsoft.MachineLearningServices/workspaces"


TEST_CLASSES_FOR_RUN_INTEGRATION_TEST_RECORDING = [
    "TestCliWithAzure",
]
