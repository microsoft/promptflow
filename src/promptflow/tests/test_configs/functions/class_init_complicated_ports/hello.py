from dataclasses import dataclass, field

from promptflow._sdk.entities import AzureOpenAIConnection


@dataclass
class ComplicatedOutput:
    s: str = "hello"
    i: int = 1
    f: float = 1.0
    b: bool = False
    d: dict = field(default_factory=dict)
    l: list = field(default_factory=list)


class Hello:
    def __init__(
        self,
        connection: AzureOpenAIConnection,
        s: str,
        i: int,
        f: float,
        b: bool,
        li: list,
        d: dict,
    ) -> None:
        pass

    def __call__(self, s: str, i: int, f: float, b: bool, li: list, d: dict) -> ComplicatedOutput:
        return ComplicatedOutput()
