from dataclasses import dataclass


@dataclass
class MyFlowOutput:
    response: str
    length: int


def hello_world(text: str) -> MyFlowOutput:
    return MyFlowOutput(
        response=f"Hello World {text}!",
        length=len(text),
    )
