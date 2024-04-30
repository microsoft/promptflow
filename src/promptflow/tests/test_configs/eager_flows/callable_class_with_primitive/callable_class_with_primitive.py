class MyFlow:
    def __init__(self, obj_input: str):
        self.obj_input = obj_input

    def __call__(self, func_input: str) -> str:
        return f"The object input is {self.obj_input} and the function input is {func_input}"

    def __aggregate__(self, results: list):
        # The item in results should be string
        assert all(isinstance(r, str) for r in results)

        return {"length": len(results)}
