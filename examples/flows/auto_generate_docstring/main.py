from dotenv import load_dotenv
from file import File
from promptflow import tool
from divider import Divider
from AzureOpenAi import ChatLLM
from prompt import PromptException, docstring_prompt


docstring = """
==class _PipelineComponentBuilderStack==
The `_PipelineComponentBuilderStack` class is used to manage a stack of `PipelineComponentBuilder` objects. It has methods to push, pop, and get the top element of the stack. It also has methods to check if the stack is empty and to get the size of the stack.

==def __init__==
The constructor of `_PipelineComponentBuilderStack` initializes an empty list to store the stack elements.

==def top==
This method returns the top element of the stack. If the stack is empty, it returns `None`.

:return: The top element of the stack.
:rtype: PipelineComponentBuilder or None

==def pop==
This method removes and returns the top element of the stack. If the stack is empty, it returns `None`.

:return: The top element of the stack.
:rtype: PipelineComponentBuilder or None

==def push==
This method adds an element to the top of the stack. It only allows pushing `PipelineComponentBuilder` elements. If the stack size exceeds the maximum depth, it raises a `UserErrorException`.

:param item: The element to be added to the stack.
:type item: PipelineComponentBuilder

:raises UserErrorException: If the stack size exceeds the maximum depth.

==def is_empty==
This method checks if the stack is empty.

:return: True if the stack is empty, False otherwise.
:rtype: bool

==def size==
This method returns the size of the stack.

:return: The size of the stack.
:rtype: int

==end==
"""


@tool
def load_code(code_path: str):
    file = File(code_path)
    return file.content()


@tool
def divide_code(file_content: str):
    divided = Divider.divide_file(file_content)
    return divided


@tool
def generate_docstring(divided: list[str]):
    llm = ChatLLM(module="gpt-35-turbo")
    res_code = []
    divided = list(reversed(divided))
    while len(divided) and len(divided) < 1000:
        item = divided.pop()
        # try:
        #     res = llm.query(docstring_prompt(item))
        #     print(res)
        # except PromptException as e:
        #     divided_tmp = Divider.divide_class_or_func(item)
        #     divided.extend(list(reversed(divided_tmp)))
        #     continue
        print(Divider.merge_doc2code(docstring, item))
        res_code.append(Divider.merge_doc2code(docstring, item))
    return res_code


@tool
def combine_code(divided: list[str]):
    code = Divider.combine(divided)
    return code


def execute_pipeline(*pipelines, args=None):
    for pipeline in pipelines:
        args = pipeline(args)
    return args


if __name__ == "__main__":
    load_dotenv()
    res = execute_pipeline(
        load_code,
        divide_code,
        generate_docstring,
        combine_code,
        args='./demo_code.py'
    )
    print(res)