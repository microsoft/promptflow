import ast
import asyncio
import logging
import sys
from promptflow import tool
from AzureOpenAi import ChatLLM
from divider import Divider
from prompt import docstring_prompt, PromptLimitException


def get_imports(content):
    tree = ast.parse(content)
    import_statements = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                import_statements.append(f"import {n.name}")
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module
            for n in node.names:
                import_statements.append(f"from {module_name} import {n.name}")

    return import_statements


async def agenerate_docstring(divided: list[str]):
    llm = ChatLLM(module="gpt-35-turbo")
    divided = list(reversed(divided))
    all_divided = []

    # If too many imports result in tokens exceeding the limit, please set an empty string.
    modules = ''  # '\n'.join(get_imports(divided[-1]))
    modules_tokens = llm.count_tokens(modules)
    if modules_tokens > 300:
        logging.warning(f'Too many imports, the number of tokens is {modules_tokens}')
    if modules_tokens > 500:
        logging.warning(f'Too many imports, the number of tokens is {modules_tokens}, will set an empty string.')
        modules = ''

    # Divide the code into two parts if the global class/function is too long.
    while len(divided):
        item = divided.pop()
        try:
            llm.validate_tokens(llm.create_prompt(docstring_prompt(item, module=modules)))
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
    for item in all_divided:
        if Divider.has_class_or_func(item):
            tasks.append(llm.aquery(docstring_prompt(item, module=modules)))
        else:  # If the code has not function or class, no need to generate docstring.
            tasks.append(asyncio.sleep(0))
    res_doc = await asyncio.gather(*tasks)
    new_code = []
    for i in range(len(all_divided)):
        if type(res_doc[i]) == str:
            new_code.append(Divider.merge_doc2code(res_doc[i], all_divided[i]))
        else:
            new_code.append(all_divided[i])

    return new_code


@tool
def generate_docstring(divided: list[str]):
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(agenerate_docstring(divided))