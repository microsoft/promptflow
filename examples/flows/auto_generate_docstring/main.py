import logging

from dotenv import load_dotenv
from file import File
from promptflow import tool
from divider import Divider
from AzureOpenAi import ChatLLM
from prompt import PromptException, docstring_prompt


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
    while len(divided) and len(divided) < 100:
        item = divided.pop()
        try:
            docstring = llm.query(docstring_prompt(item))
        except PromptException as e:
            logging.warning(e.message + ', will divide the code into two parts.')
            divided_tmp = Divider.divide_half(item)
            if len(divided_tmp) > 1:
                divided.extend(list(reversed(divided_tmp)))
                continue
            else:
                logging.warning('The code is too short and divide fail, will not generate docstring.')
                docstring = ''
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
    # code = open('./test.txt', "r").read()
    # doc = open('./test2.txt', "r").read()
    # print(Divider.merge_doc2code(doc, code))
    # print(combine_code(generate_docstring([text])))
    # functions, pos = Divider.get_functions_and_pos(text)
    # for func in functions:
    #     print(func)