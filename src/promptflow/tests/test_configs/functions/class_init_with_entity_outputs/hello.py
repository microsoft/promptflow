from typing import List


class CustomEntity:
    def __init__(self):
        pass

    def __str__(self):
        return "CustomEntity"


class Hello:
    def __init__(self, words: str):
        self.words = words

    def __call__(self, text: str) -> CustomEntity:
        return CustomEntity()
