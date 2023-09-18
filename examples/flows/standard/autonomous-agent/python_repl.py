import sys
from io import StringIO
import functools
import logging
import ast
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=None)
def warn_once() -> None:
    # Warn that the PythonREPL
    logger.warning("Python REPL can execute arbitrary code. Use with caution.")


COMMAND_EXECUTION_FUNCTIONS = ["system", "exec", "execfile", "eval"]


class PythonValidation:

    def __init__(
        self,
        allow_imports: bool = False,
        allow_command_exec: bool = False,
    ):
        """Initialize a PALValidation instance.

        Args:
            allow_imports (bool): Allow import statements.
            allow_command_exec (bool): Allow using known command execution functions.
        """
        self.allow_imports = allow_imports
        self.allow_command_exec = allow_command_exec

    def validate_code(self, code: str) -> None:
        try:
            code_tree = ast.parse(code)
        except (SyntaxError, UnicodeDecodeError):
            raise ValueError(f"Generated code is not valid python code: {code}")
        except TypeError:
            raise ValueError(
                f"Generated code is expected to be a string, "
                f"instead found {type(code)}"
            )
        except OverflowError:
            raise ValueError(
                f"Generated code too long / complex to be parsed by ast: {code}"
            )

        has_imports = False
        top_level_nodes = list(ast.iter_child_nodes(code_tree))
        for node in top_level_nodes:
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                has_imports = True

        if not self.allow_imports and has_imports:
            raise ValueError(f"Generated code has disallowed imports: {code}")

        if (
            not self.allow_command_exec
            or not self.allow_imports
        ):
            for node in ast.walk(code_tree):
                if (
                    (not self.allow_command_exec)
                    and isinstance(node, ast.Call)
                    and (
                        (
                            hasattr(node.func, "id")
                            and node.func.id in COMMAND_EXECUTION_FUNCTIONS
                        )
                        or (
                            isinstance(node.func, ast.Attribute)
                            and node.func.attr in COMMAND_EXECUTION_FUNCTIONS
                        )
                    )
                ):
                    raise ValueError(
                        f"Found illegal command execution function "
                        f"{node.func.id} in code {code}"
                    )

                if (not self.allow_imports) and (
                    isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom)
                ):
                    raise ValueError(f"Generated code has disallowed imports: {code}")


class PythonREPL:
    """Simulates a standalone Python REPL."""

    def __init__(self) -> None:
        self.globals: Optional[Dict] = globals()
        self.locals: Optional[Dict] = None
        self.code_validations = PythonValidation(allow_imports=True)

    def run(self, command: str) -> str:
        """Run command with own globals/locals and returns anything printed."""

        # Warn against dangers of PythonREPL
        warn_once()
        self.code_validations.validate_code(command)
        old_stdout = sys.stdout
        sys.stdout = my_stdout = StringIO()
        try:
            exec(command, self.globals, self.locals)
            sys.stdout = old_stdout
            output = my_stdout.getvalue()
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
