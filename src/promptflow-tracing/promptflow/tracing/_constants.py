# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class ResourceAttributesFieldName:
    SERVICE_NAME = "service.name"
    COLLECTION = "collection"


RESOURCE_ATTRIBUTES_SERVICE_NAME = "promptflow"
RESOURCE_ATTRIBUTES_COLLECTION_DEFAULT = "default"

PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON = "PF_TRACING_SKIP_LOCAL_SETUP"
# Currently OTel doesn't have an official env var for setting events api endpoint,
# we define pf specific env var for our own usage.
PF_EVENT_LOGGER_ENDPOINT = "PF_EVENT_LOGGER_ENDPOINT"
