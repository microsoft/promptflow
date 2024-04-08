# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# Prompt
DEFAULT_PROMPT_TEMPLATE = """# Labeling Guidelines
{labeling_guidelines}

# Labeled Examples
{few_shot_examples}
{input_examples}
"""
DEFAULT_FEW_SHOT_EXAMPLE_PATTERN = "Example #{example_index}:\nInput:\n{inputs}\nOutput:\n{labels}\n"
DEFAULT_FEW_SHOT_EXAMPLE_SEPARATOR = "\n"
DEFAULT_INPUT_EXAMPLE_PATTERN = "Example #{example_index}:\nInput:\n{inputs}\n"
DEFAULT_INPUT_EXAMPLE_SEPARATOR = "\n"
DEFAULT_MAX_SHOTS = 5
DEFAULT_MAX_INPUTS = 1
DEFAULT_MIN_SHOTS = 1
DEFAULT_MIN_INPUTS = 1


# Model defaults
DEFAULT_STOP = '"<|im_end|>"'
DEFAULT_MODEL = "gpt-4"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TOP_P = 1.0
DEFAULT_NUM_SAMPLES = 1
DEFAULT_LOGPROBS = None
DEFAULT_SAMPLE_LEN = 2000
DEFAULT_FREQUENCY_PENALTY = 0.5
DEFAULT_PRESENCE_PENALTY = 0.0

# Metric stability defaults
DEFAULT_STABILITY_LEVEL = "regular"
STABILITY_VALUES = {"regular": 1, "high": 3, "maximum": 5}

# Endpoint defaults
DEFAULT_API_CALL_MAX_PARALLEL_COUNT = 1
DEFAULT_REQUEST_ERROR_RATE_THRESHOLD = 0.5
DEFAULT_API_CALL_DELAY_SEC = 0.5
DEFAULT_API_CALL_RETRY_SLEEP_SEC = 10
DEFAULT_API_CALL_RETRY_MAX_COUNT = 3
DEFAULT_USE_OAI_ENDPOINT_OUTPUT_FORMAT = False
DEFAULT_AUTHORIZATION_USE_OCP_SUBSCRIPTION_KEY = False


# Authorization defaults
DEFAULT_AUTHORIZATION_TYPE = "managed_identity"
DEFAULT_AUTHORIZATION_HEADER = "Bearer"
