from dataclasses import dataclass


@dataclass
class Data:
    text: str
    models: list


def my_flow(text: str = "default_text", models: list = ["default_model"]) -> Data:
    return Data(text=text, models=models)
