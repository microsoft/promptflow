# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import time
from typing import Optional

import tiktoken


class Tokenizer:
    """Handles LLM tokenizing using the tiktoken library."""

    def __init__(self, model_name: str, logger: Optional[logging.Logger] = None):
        self.model_name = model_name
        self.logger = logger

        # Get fast tokenizer for model_name
        # NOTE: will look for models with alike prefixes if not found directly
        self.set_encoding(model_name)

    def count_tokens(self, input: str) -> int:
        # Count tokens, including special tokens like <|endofprompt|>
        return len(self.encoding.encode(input, allowed_special="all"))

    def set_encoding(self, model_name: str) -> None:
        # See: tiktoken mapping of model names here:
        #  https://github.com/openai/tiktoken/blob/main/tiktoken/model.py#L12

        start = time.time()

        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self._log(f"Couldn't find encoding for '{model_name}'", log_level=logging.WARNING)

            # if chat model, return chat encoding
            if "chat" in model_name or "gpt-3.5" in model_name:
                encoding = tiktoken.get_encoding("cl100k_base")

            else:
                # Default to encoding for text & codex models
                encoding = tiktoken.get_encoding("p50k_base")

        end = time.time()

        self._log(f"Encoder set to '{encoding.name}'. " + f"Took {(end - start) * 1e3:.2f}ms to load.")

        self.encoding = encoding

    def _log(self, message: str, log_level: int = logging.INFO):
        if self.logger:
            self.logger.log(log_level, message)
