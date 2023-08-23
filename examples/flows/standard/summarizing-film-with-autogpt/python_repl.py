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


class PALValidation:
    SOLUTION_EXPRESSION_TYPE_FUNCTION = ast.FunctionDef
    SOLUTION_EXPRESSION_TYPE_VARIABLE = ast.Name

    def __init__(
        self,
        solution_expression_name: Optional[str] = None,
        solution_expression_type: Optional[type] = None,
        allow_imports: bool = False,
        allow_command_exec: bool = False,
    ):
        """Initialize a PALValidation instance.

        Args:
            solution_expression_name (str): Name of the expected solution expression.
                If passed, solution_expression_type must be passed as well.
            solution_expression_type (str): AST type of the expected solution
                expression. If passed, solution_expression_name must be passed as well.
                Must be one of PALValidation.SOLUTION_EXPRESSION_TYPE_FUNCTION,
                PALValidation.SOLUTION_EXPRESSION_TYPE_VARIABLE.
            allow_imports (bool): Allow import statements.
            allow_command_exec (bool): Allow using known command execution functions.
        """
        self.solution_expression_name = solution_expression_name
        self.solution_expression_type = solution_expression_type

        if solution_expression_name is not None:
            if not isinstance(self.solution_expression_name, str):
                raise ValueError(
                    f"Expected solution_expression_name to be str, "
                    f"instead found {type(self.solution_expression_name)}"
                )
        if solution_expression_type is not None:
            if (
                self.solution_expression_type
                is not self.SOLUTION_EXPRESSION_TYPE_FUNCTION
                and self.solution_expression_type
                is not self.SOLUTION_EXPRESSION_TYPE_VARIABLE
            ):
                raise ValueError(
                    f"Expected solution_expression_type to be one of "
                    f"({self.SOLUTION_EXPRESSION_TYPE_FUNCTION},"
                    f"{self.SOLUTION_EXPRESSION_TYPE_VARIABLE}),"
                    f"instead found {self.solution_expression_type}"
                )

        if solution_expression_name is not None and solution_expression_type is None:
            raise TypeError(
                "solution_expression_name "
                "requires solution_expression_type to be passed as well"
            )
        if solution_expression_name is None and solution_expression_type is not None:
            raise TypeError(
                "solution_expression_type "
                "requires solution_expression_name to be passed as well"
            )

        self.allow_imports = allow_imports
        self.allow_command_exec = allow_command_exec
        
        
    @classmethod
    def validate_code(cls, code: str) -> None:
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

        found_solution_expr = False
        if cls.solution_expression_name is None:
            # Skip validation if no solution_expression_name was given
            found_solution_expr = True

        has_imports = False
        top_level_nodes = list(ast.iter_child_nodes(code_tree))
        for node in top_level_nodes:
            if (
                cls.solution_expression_name is not None
                and cls.solution_expression_type is not None
            ):
                # Check root nodes (like func def)
                if (
                    isinstance(node, cls.solution_expression_type)
                    and hasattr(node, "name")
                    and node.name == cls.solution_expression_name
                ):
                    found_solution_expr = True
                # Check assigned nodes (like answer variable)
                if isinstance(node, ast.Assign):
                    for target_node in node.targets:
                        if (
                            isinstance(
                                target_node, cls.solution_expression_type
                            )
                            and hasattr(target_node, "id")
                            and target_node.id
                            == cls.solution_expression_name
                        ):
                            found_solution_expr = True
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                has_imports = True

        if not found_solution_expr:
            raise ValueError(
                f"Generated code is missing the solution expression: "
                f"{cls.solution_expression_name} of type: "
                f"{cls.solution_expression_type}"
            )

        if not cls.allow_imports and has_imports:
            raise ValueError(f"Generated code has disallowed imports: {code}")

        if (
            not cls.allow_command_exec
            or not cls.allow_imports
        ):
            for node in ast.walk(code_tree):
                if (
                    (not cls.allow_command_exec)
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

                if (not cls.allow_imports) and (
                    isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom)
                ):
                    raise ValueError(f"Generated code has disallowed imports: {code}")
                

class PythonREPL:
    """Simulates a standalone Python REPL."""

    def __init__(self) -> None:
        self.globals: Optional[Dict] = globals()
        self.locals: Optional[Dict] = None

    def run(self, command: str) -> str:
        """Run command with own globals/locals and returns anything printed."""

        # Warn against dangers of PythonREPL
        warn_once()

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
