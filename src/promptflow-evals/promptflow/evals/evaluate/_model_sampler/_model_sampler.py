import copy
import os
import re

from promptflow.core import Prompty


class ModelSampler:
    def __init__(self, model_config, trajectory, sampling_params):
        if model_config.api_version is None:
            model_config.api_version = "2024-02-15-preview"

        prompty_model_config = {"configuration": model_config, "parameters": sampling_params}
        current_dir = os.path.dirname(__file__)
        prompty_path = os.path.join(current_dir, "model_sampler.prompty")

        self._flow = Prompty.load(source=prompty_path, model=prompty_model_config)
        self._trajectory = trajectory

    def __call__(self, *, line_data, **kwargs):
        messages = copy.deepcopy(self._trajectory)

        for message in messages:
            message["content"] = self.resolve_placeholders(message["content"], line_data)

        # for message in messages:
        #     print(f"{message['role']}: {message['content']}")

        llm_output = self._flow(trajectory=messages, timeout=600)

        return {"sample": llm_output}

    def resolve_placeholders(self, content, line_data):
        pattern = re.compile(r"\$\{data\.(\w+)\}")

        def replace(match):
            key = match.group(1)
            if key not in line_data:
                raise KeyError(f'Reference "${{data.{key}}}" not found in data')

            return line_data[key]

        return pattern.sub(replace, content)
