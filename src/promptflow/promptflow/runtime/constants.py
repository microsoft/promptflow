# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class DefaultConfig(object):
    DEV = "dev"
    MIR = "mir"
    PYMT = "pymt"


DEFAULT_CONFIGS = [getattr(DefaultConfig, k) for k in dir(DefaultConfig) if k.isupper()]

PRT_CONFIG_FILE = "prt.yaml"

PRT_CONFIG_OVERRIDE_ENV = "PRT_CONFIG_OVERRIDE"
PRT_CONFIG_FILE_ENV = "PRT_CONFIG_FILE"
PROMPTFLOW_PROJECT_PATH = "PROMPTFLOW_PROJECT_PATH"
PROMPTFLOW_ENCODED_CONNECTIONS = "PROMPTFLOW_ENCODED_CONNECTIONS"
