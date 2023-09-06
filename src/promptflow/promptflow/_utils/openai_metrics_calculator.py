import tiktoken


class OpenAIMetricsCalculator:
    def __init__(self, logger=None) -> None:
        self._logger = logger

    def get_openai_metrics_from_api_call(self, api_call: dict):
        total_metrics = {}
        if self._need_collect_metrics(api_call):
            metrics = self._get_openai_metrics_for_signal_api(api_call)
            self.merge_metrics_dict(total_metrics, metrics)

        children = api_call.get("children")
        if children is not None:
            for child in children:
                child_metrics = self.get_openai_metrics_from_api_call(child)
                self.merge_metrics_dict(total_metrics, child_metrics)

        return total_metrics

    def _need_collect_metrics(self, api_call: dict):
        if api_call.get("type") != "LLM":
            return False
        output = api_call.get("output")
        if not isinstance(output, dict) and not isinstance(output, list):
            return False
        return True

    def _get_openai_metrics_for_signal_api(self, api_call: dict):
        output = api_call.get("output")
        if isinstance(output, dict):
            usage = output.get("usage")
            if isinstance(usage, dict):
                return usage
            self._log_warning("Cannot find usage in output, will calculate metrics from response data directly.")

        name = api_call.get("name")
        if name.split(".")[-2] == "ChatCompletion":
            return self._get_openai_metrics_for_chat_api(api_call)
        elif name.split(".")[-2] == "Completion":
            return self._get_openai_metrics_for_completion_api(api_call)
        else:
            self._log_warning(f"Cannot calculate metrics for api: {name}.")
            return {}

    def _get_openai_metrics_for_chat_api(self, api_call):
        inputs = api_call.get("inputs")
        output = api_call.get("output")
        metrics = {}
        enc, tokens_per_message, tokens_per_name = self._get_encoding_for_chat_api(inputs["engine"])
        metrics["prompt_tokens"] = self._get_prompt_tokens_from_messages(
            inputs["messages"],
            enc,
            tokens_per_message,
            tokens_per_name
        )
        if isinstance(output, list):
            metrics["completion_tokens"] = len(output)
        else:
            metrics["completion_tokens"] = self._get_completion_tokens_for_chat_api(output, enc)
        metrics["total_tokens"] = metrics["prompt_tokens"] + metrics["completion_tokens"]
        return metrics

    def _get_encoding_for_chat_api(self, model):
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        if model in {
            "gpt-35-turbo-0613",
            "gpt-35-turbo-16k-0613",
            "gpt-4-0314",
            "gpt-4-32k-0314",
            "gpt-4-0613",
            "gpt-4-32k-0613",
        }:
            tokens_per_message = 3
            tokens_per_name = 1
        elif model == "gpt-35-turbo-0301":
            tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
            tokens_per_name = -1  # if there's a name, the role is omitted
        elif "gpt-35-turbo" in model:
            return self._get_encoding_for_chat_api(model="gpt-35-turbo-0613")
        elif "gpt-4" in model:
            return self._get_encoding_for_chat_api(model="gpt-4-0613")
        else:
            self._log_warning(f"Cannot find encoding for model: {model}, will use default encoding.")
            return self._get_encoding_for_chat_api(model="gpt-35-turbo-0613")
        return enc, tokens_per_message, tokens_per_name

    def _get_prompt_tokens_from_messages(self, messages, enc, tokens_per_message, tokens_per_name):
        prompt_tokens = 0
        for message in messages:
            prompt_tokens += tokens_per_message
            for key, value in message.items():
                prompt_tokens += len(enc.encode(value))
                if key == "name":
                    prompt_tokens += tokens_per_name
        prompt_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
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

    def _get_openai_metrics_for_completion_api(self, api_call: dict):
        metrics = {}
        inputs = api_call.get("inputs")
        output = api_call.get("output")
        enc = self._get_encoding_for_completion_api(inputs["engine"])
        metrics["prompt_tokens"] = 0
        prompt = inputs.get("prompt")
        if isinstance(prompt, str):
            metrics["prompt_tokens"] = len(enc.encode(prompt))
        elif isinstance(prompt, list):
            for pro in prompt:
                metrics["prompt_tokens"] += len(enc.encode(pro))
        if isinstance(output, list):
            metrics["completion_tokens"] = len(output)
        else:
            metrics["completion_tokens"] = self._get_completion_tokens_for_completion_api(output)
        metrics["total_tokens"] = metrics["prompt_tokens"] + metrics["completion_tokens"]
        return metrics

    def _get_encoding_for_completion_api(self, model):
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("p50k_base")
        return enc

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
