import sys
from promptflow.tools.common import render_jinja_template
from divider import Divider


class PromptException(Exception):
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


def docstring_prompt(code: str, module: str='') -> str:
    functions = Divider.get_functions(code)
    with open('doc_format.jinja2') as file:
        return render_jinja_template(prompt=file.read(), module=module, code=code, functions=functions)