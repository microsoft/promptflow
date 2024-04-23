from promptflow import tool
class MyDict(dict):
    pass

@tool
def return_dict(input1: str):
    return MyDict(input1=input1)
