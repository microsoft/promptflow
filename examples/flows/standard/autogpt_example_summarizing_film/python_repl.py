import sys
from io import StringIO
from typing import Dict, Optional


class PythonREPL:
    """Simulates a standalone Python REPL."""

    def __init__(self) -> None:
        self.globals: Optional[Dict] = globals()
        self.locals: Optional[Dict] = None

    def run(self, command: str) -> str:
        """Run command with own globals/locals and returns anything printed."""
        old_stdout = sys.stdout
        sys.stdout = mystdout = StringIO()
        try:
            exec(command, self.globals, self.locals)
            sys.stdout = old_stdout
            output = mystdout.getvalue()
        except Exception as e:
            sys.stdout = old_stdout
            output = repr(e)
        print(output)
        return output


python_repl = PythonREPL()


def python(command: str):
    """
    A Python shell. Use this to execute python commands. Input should be a valid python command.
    If you want to see the output of a value, you should print it out with `print(...)`.
    """

    command = command.strip().strip("```")
    return python_repl.run(command)
