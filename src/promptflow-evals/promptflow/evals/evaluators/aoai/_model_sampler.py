import re


class ModelSampler:
    def __init__(self, model_config, trajectory):
        self._model_config = model_config
        self.trajectory = trajectory

    def __call__(self, line_data):
        for message in self.trajectory:
            message["content"] = self.resolve_placeholders(message["content"], line_data)

        for message in self.trajectory:
            print(f"{message['role']}: {message['content']}")

    def resolve_placeholders(self, content, line_data):
        pattern = re.compile(r"\$\{data\.(\w+)\}")

        def replace(match):
            key = match.group(1)
            if key not in line_data:
                raise KeyError(f"Reference {key} not found in line_data")
            return line_data[key]

        return pattern.sub(replace, content)


# Example usage
trajectory = [
    {"role": "system", "content": "Initializing conversation with ${data.name} about ${data.subject}."},
    {"role": "user", "content": "hello ${data.name}, how are you?"},
    {"role": "assistant", "content": "I'm doing well, thank you! What can I help you with today, ${data.name}?"},
    {"role": "user", "content": "I need information about ${data.subject}."},
    {"role": "assistant", "content": "Sure, I can help with that. Here is what I found on ${data.subject}."},
]

line_data = {"name": "Alice", "subject": "Python programming"}

model_sampler = ModelSampler(model_config={}, trajectory=trajectory)
model_sampler(line_data)
