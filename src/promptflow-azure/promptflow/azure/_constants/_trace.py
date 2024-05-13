# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

COSMOS_DB_SETUP_POLL_TIMEOUT_SECOND = 600
COSMOS_DB_SETUP_POLL_INTERVAL_SECOND = 30
COSMOS_DB_SETUP_POLL_PRINT_INTERVAL_SECOND = 30
COSMOS_DB_SETUP_RESOURCE_TYPE = "HOBO"


class CosmosConfiguration:
    NONE = "None"
    READ_DISABLED = "ReadDisabled"
    WRITE_DISABLED = "WriteDisabled"
    DISABLED = "Disabled"
    DIAGNOSTIC_DISABLED = "DiagnosticDisabled"
    DATA_CLEANED = "DataCleaned"
    ACCOUNT_DELETED = "AccountDeleted"


class CosmosStatus:
    NOT_EXISTS = "NotExists"
    INITIALIZING = "Initializing"
    INITIALIZED = "Initialized"
    DELETING = "Deleting"
    DELETED = "Deleted"
    NOT_AVAILABLE = "NotAvailable"
