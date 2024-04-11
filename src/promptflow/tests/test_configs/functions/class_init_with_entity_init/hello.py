class CustomConfig:
    def __init__(self, words: list) -> None:
        self.words = words


class Hello:
    def __init__(self, words: CustomConfig) -> None:
        self.words = words.words

    def __call__(self, text: str) -> str:
        return f"Hello {','.join(self.words)} {text}!"
