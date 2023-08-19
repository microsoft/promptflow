import asyncio
import logging
import time

from dotenv import load_dotenv
from file import File
from promptflow import tool
from divider import Divider
from AzureOpenAi import ChatLLM, LLM
from prompt import PromptLimitException, docstring_prompt
from diff import show_diff


@tool
def load_code(code_path: str):
    file = File(code_path)
    return file.content()


@tool
def divide_code(file_content: str):
    # Divide the code into several parts according to the global import/class/function.
    divided = Divider.divide_file(file_content)
    return divided


async def agenerate_docstring(divided: list[str]):
    llm = LLM(module="gpt-35-turbo")
    divided = list(reversed(divided))
    all_divided = []

    # Divide the code into two parts if the global class/function is too long.
    while len(divided):
        item = divided.pop()
        try:
            llm.validate_tokens(llm.create_prompt(docstring_prompt(item)))
        except PromptLimitException as e:
            logging.warning(e.message + ', will divide the code into two parts.')
            divided_tmp = Divider.divide_half(item)
            if len(divided_tmp) > 1:
                divided.extend(list(reversed(divided_tmp)))
                continue
            else:
                logging.warning(f'The code is too long, will not generate docstring.')
        except Exception as e:
            logging.warning(e)
        all_divided.append(item)

    tasks = []
    new_code = []
    for item in all_divided:
        tasks.append(llm.aquery(docstring_prompt(item)))
    res_doc = await asyncio.gather(*tasks, return_exceptions=True)
    for i in range(len(all_divided)):
        if type(res_doc[i]) == str:
            new_code.append(Divider.merge_doc2code(res_doc[i], all_divided[i]))
        else:
            new_code.append(all_divided[i])

    return new_code


@tool
def generate_docstring(divided: list[str]):
    return asyncio.run(agenerate_docstring(divided))


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
    # res = execute_pipeline(
    #     load_code,
    #     divide_code,
    #     generate_docstring,
    #     combine_code,
    #     args='./demo_code.py'
    # )
    # print(res)
    code = open('./test.txt', "r").read()
    # doc = open('./test2.txt', "r").read()
    # print(Divider.merge_doc2code(doc, code))
    print(combine_code(generate_docstring([code])))
    # functions, pos = Divider.get_functions_and_pos(text)
    # for func in functions:
    #     print(func)