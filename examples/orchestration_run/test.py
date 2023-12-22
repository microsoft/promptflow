from typing import List, NamedTuple


def f() -> NamedTuple("Output", [("output_dir", str), ("accuracy", float), ("result", List[str])]):
    return {"output_dir": "123", "accuracy": 456, "result": [7, 8, 9]}


if __name__ == "__main__":
    print(f())
    # inspect.signature(f).return_annotation.__annotations__["result"]
