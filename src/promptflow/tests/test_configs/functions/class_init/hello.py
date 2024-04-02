
class Hello:
    def __init__(self, background: str) -> None:
        self.background = background

    def __call__(self, text: str) -> str:
        return f"Hello {self.background} {text}!"
