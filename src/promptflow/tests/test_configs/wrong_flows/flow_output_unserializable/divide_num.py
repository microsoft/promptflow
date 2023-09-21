from promptflow import tool


@tool
def divide_num(num: int):
    return UnserializableClass(num=(int)(num / 2))


class UnserializableClass:
    def __init__(self, num: int):
        self.num = num

    def __str__(self):
        return str(self.num)