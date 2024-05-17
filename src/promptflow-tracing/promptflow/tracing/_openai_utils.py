from abc import ABC, abstractmethod
from importlib.metadata import version

import tiktoken

IS_LEGACY_OPENAI = version("openai").startswith("0.")


class OpenAIMetricsCalculator:
    def __init__(self, logger=None) -> None:
        self._logger = logger

    def get_openai_metrics_from_api_call(self, api_call: dict):
        total_metrics = {}
        if self._need_collect_metrics(api_call):
            try:
                metrics = self._get_openai_metrics_for_signal_api(api_call)
                self.merge_metrics_dict(total_metrics, metrics)
            except Exception as ex:
                self._log_warning(f"Failed to calculate metrics due to exception: {ex}.")

        children = api_call.get("children")
        if children is not None:
            for child in children:
                child_metrics = self.get_openai_metrics_from_api_call(child)
                self.merge_metrics_dict(total_metrics, child_metrics)
        api_call["system_metrics"] = total_metrics
        return total_metrics

    def _need_collect_metrics(self, api_call: dict):
        if api_call.get("type") != "LLM":
            return False
        output = api_call.get("output")
        if not isinstance(output, dict) and not isinstance(output, list):
            return False
        inputs = api_call.get("inputs")
        if not isinstance(inputs, dict):
            return False
        return True

    def _get_openai_metrics_for_signal_api(self, api_call: dict):
        inputs = api_call.get("inputs")
        output = api_call.get("output")
        if isinstance(output, dict):
            usage = output.get("usage")
            if isinstance(usage, dict):
                return usage
            self._log_warning(
                "Cannot find openai metrics in output, will calculate metrics from response data directly."
            )

        name = api_call.get("name")
        # Support both legacy api and OpenAI v1 api
        # Legacy api:
        #   https://github.com/openai/openai-python/blob/v0.28.1/openai/api_resources/chat_completion.py
        #   https://github.com/openai/openai-python/blob/v0.28.1/openai/api_resources/completion.py
        # OpenAI v1 api:
        #   https://github.com/openai/openai-python/blob/main/src/openai/resources/chat/completions.py
        #   https://github.com/openai/openai-python/blob/main/src/openai/resources/completions.py
        if name == "openai_chat_legacy" or name == "openai_chat":  # openai v1
            return self.get_openai_metrics_for_chat_api(inputs, output)
        elif name == "openai_completion_legacy" or name == "openai_completion":  # openai v1
            return self.get_openai_metrics_for_completion_api(inputs, output)
        else:
            raise Exception(f"Calculating metrics for api {name} is not supported.")

    def _try_get_model(self, inputs, output):
        if IS_LEGACY_OPENAI:
            api_type = inputs.get("api_type")
            if not api_type:
                raise Exception("Cannot calculate metrics for none or empty api_type.")
            if api_type == "azure":
                model = inputs.get("engine")
            else:
                model = inputs.get("model")
        else:
            if isinstance(output, dict):
                model = output.get("model")
            else:
                model = None
                for chunk in output:
                    if hasattr(chunk, "model"):
                        model = chunk.model
                        break
            if not model:
                model = inputs.get("model")
        if not model:
            raise Exception(
                "Cannot get a valid model to calculate metrics."
                "Please specify a engine for AzureOpenAI API or a model for OpenAI API."
            )
        return model

    def get_openai_metrics_for_chat_api(self, inputs, output):
        metrics = {}
        try:
            enc, tokens_per_message, tokens_per_name = self._get_encoding_for_chat_api(
                self._try_get_model(inputs, output)
            )
            metrics["prompt_tokens"] = self._get_prompt_tokens_from_messages(
                inputs["messages"], enc, tokens_per_message, tokens_per_name
            )
            if isinstance(output, list):
                if IS_LEGACY_OPENAI:
                    metrics["completion_tokens"] = len(output)
                else:
                    metrics["completion_tokens"] = len(
                        [chunk for chunk in output if chunk.choices and chunk.choices[0].delta.content]
                    )
            else:
                metrics["completion_tokens"] = self._get_completion_tokens_for_chat_api(output, enc)
            metrics["total_tokens"] = metrics["prompt_tokens"] + metrics["completion_tokens"]
        except Exception as ex:
            self._log_warning(f"Failed to calculate metrics due to exception: {ex}.")
        return metrics

    def _get_encoding_for_chat_api(self, model):
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        if model == "gpt-35-turbo-0301":
            tokens_per_message = 4
            tokens_per_name = -1
        elif "gpt-35-turbo" in model or "gpt-3.5-turbo" in model or "gpt-4" in model:
            tokens_per_message = 3
            tokens_per_name = 1
        else:
            raise Exception(f"Calculating metrics for model {model} is not supported.")
        return enc, tokens_per_message, tokens_per_name

    def _get_prompt_tokens_from_messages(self, messages, enc, tokens_per_message, tokens_per_name):
        prompt_tokens = 0
        for message in messages:
            prompt_tokens += tokens_per_message
            for key, value in message.items():
                prompt_tokens += len(enc.encode(value))
                if key == "name":
                    prompt_tokens += tokens_per_name
        prompt_tokens += 3
        return prompt_tokens

    def _get_completion_tokens_for_chat_api(self, output, enc):
        completion_tokens = 0
        choices = output.get("choices")
        if isinstance(choices, list):
            for ch in choices:
                if isinstance(ch, dict):
                    message = ch.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")
                        if isinstance(content, str):
                            completion_tokens += len(enc.encode(content))
        return completion_tokens

    def get_openai_metrics_for_completion_api(self, inputs, output):
        metrics = {}
        try:
            enc = self._get_encoding_for_completion_api(self._try_get_model(inputs, output))
            metrics["prompt_tokens"] = 0
            prompt = inputs.get("prompt")
            if isinstance(prompt, str):
                metrics["prompt_tokens"] = len(enc.encode(prompt))
            elif isinstance(prompt, list):
                for pro in prompt:
                    metrics["prompt_tokens"] += len(enc.encode(pro))
            if isinstance(output, list):
                if IS_LEGACY_OPENAI:
                    metrics["completion_tokens"] = len(output)
                else:
                    metrics["completion_tokens"] = len(
                        [chunk for chunk in output if chunk.choices and chunk.choices[0].text]
                    )
            else:
                metrics["completion_tokens"] = self._get_completion_tokens_for_completion_api(output, enc)
            metrics["total_tokens"] = metrics["prompt_tokens"] + metrics["completion_tokens"]
        except Exception as ex:
            self._log_warning(f"Failed to calculate metrics due to exception: {ex}.")
        return metrics

    def _get_encoding_for_completion_api(self, model):
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            return tiktoken.get_encoding("p50k_base")

    def _get_completion_tokens_for_completion_api(self, output, enc):
        completion_tokens = 0
        choices = output.get("choices")
        if isinstance(choices, list):
            for ch in choices:
                if isinstance(ch, dict):
                    text = ch.get("text")
                    if isinstance(text, str):
                        completion_tokens += len(enc.encode(text))
        return completion_tokens

    def merge_metrics_dict(self, metrics: dict, metrics_to_merge: dict):
        for k, v in metrics_to_merge.items():
            metrics[k] = metrics.get(k, 0) + v

    def _log_warning(self, msg):
        if self._logger:
            self._logger.warning(msg)


class OpenAIResponseParser(ABC):
    def __init__(self, response, is_chat):
        self._response = response
        self._is_chat = is_chat

    @property
    def model(self):
        """
        This method iterates over each item in the _response list.
        If the item has a non-empty 'model' attribute, it returns the model.
        If no such item is found, it returns None.
        """
        for response_item in self._response:
            if hasattr(response_item, "model") and response_item.model:
                return response_item.model
        return None

    @property
    def is_chat(self):
        return self._is_chat

    @staticmethod
    def init_parser(response):
        if IS_LEGACY_OPENAI:
            return None

        from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
        from openai.types.completion import Completion

        if response and isinstance(response[0], ChatCompletionChunk):
            return OpenAIChatResponseParser(response, True)
        elif response and isinstance(response[0], Completion):
            return OpenAICompletionResponseParser(response, False)
        else:
            raise NotImplementedError("Only support 'ChatCompletionChunk' and 'Completion' response.")

    @abstractmethod
    def get_generated_message(self):
        pass


class OpenAIChatResponseParser(OpenAIResponseParser):
    def __init__(self, response, is_chat):
        super().__init__(response, is_chat)

    def get_generated_message(self):
        chunks = []
        role = "assistant"
        for item in self._response:
            if item.choices and item.choices[0].delta.content:
                chunks.append(item.choices[0].delta.content)
                role = item.choices[0].delta.role or role
        return {"content": "".join(chunks), "role": role} if chunks else None


class OpenAICompletionResponseParser(OpenAIResponseParser):
    def __init__(self, response, is_chat):
        super().__init__(response, is_chat)

    def get_generated_message(self):
        chunks = []
        for item in self._response:
            if item.choices and item.choices[0].text:
                chunks.append(item.choices[0].text)
        return "".join(chunks) if chunks else None
