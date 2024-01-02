from promptflow import tool
from promptflow.contracts.multimedia import Image, Text


@tool
def passthrough(image: Image, question: list, chat_history: list):
    assert_contain_image_and_text(image)
    assert_contain_image_and_text(question)
    assert_contain_image_and_text(chat_history)
    return question


def assert_contain_image_and_text(value: any):
    if isinstance(value, list):
        for v in value:
            assert_contain_image_and_text(v)
    elif isinstance(value, dict):
        for _, v in value.items():
            assert_contain_image_and_text(v)
    else:
        assert isinstance(value, (Image, Text))
