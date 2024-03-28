# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

class MyFlow:
    def __init__(self):
        raise Exception("This is an exception")

    def __call__(self, func_input: str) -> dict:
        return {
            "func_input": func_input,
            "obj_id": id(self),
        }


if __name__ == "__main__":
    flow = MyFlow()
    result = flow("func_input")
    print(result)

