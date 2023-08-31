import sys
from promptflow.tools.common import render_jinja_template
from divider import Divider


class PromptLimitException(Exception):
    def __init__(self, message="", **kwargs):
        super().__init__(message, **kwargs)
        self._message = str(message)
        self._kwargs = kwargs
        self._inner_exception = kwargs.get("error")
        self.exc_type, self.exc_value, self.exc_traceback = sys.exc_info()
        self.exc_type = self.exc_type.__name__ if self.exc_type else type(self._inner_exception)
        self.exc_msg = "{}, {}: {}".format(message, self.exc_type, self.exc_value)

    @property
    def message(self):
        if self._message:
            return self._message

        return self.__class__.__name__


def docstring_prompt(last_code: str = '', code: str = '', module: str = '') -> str:
    functions, _ = Divider.get_functions_and_pos(code)
    # Add the first few lines to the function, such as decorator, to make the docstring generated better by llm.
    first_three_lines = '\n'.join(last_code.split('\n')[-3:])
    with open('doc_format.jinja2') as file:
        return render_jinja_template(prompt=file.read(), module=module.strip('\n'),
                                     code=(first_three_lines + code).strip('\n'), functions=functions)
