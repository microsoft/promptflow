class MyClass:
    def __init__(self, input_init: str = None):
        self.input_init = input_init

    def __call__(self, input_1: str, input_2: str = None):
        assert self.input_init is None
        assert input_2 is None
        return "dummy_output"
