class MyClass:
    def __init__(self, input_init: str = "default_input_init"):
        pass

    def __call__(self, input_1, input_2: str = "default_input_2"):
        return {"output": input_2}
