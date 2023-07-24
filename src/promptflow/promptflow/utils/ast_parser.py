import ast


class AstParser:
    """A class that can parse the python code using AST."""

    def __init__(self, code: str):
        self._ast = ast.parse(code)

    def list_functions(self):
        """List all the FunctionDef in the ast."""
        result = []

        class FunctionVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                result.append(node)

        FunctionVisitor().visit(self._ast)
        return result

    def get_function(self, name):
        """Get the analyzer of the function with the given name."""
        function_def = next((f for f in self.list_functions() if f.name == name), None)
        if not function_def:
            raise ValueError(f"Function {name} not found.")
        return FunctionDefAnalyzer(function_def)


class FunctionDefAnalyzer:
    """A class that can analyze FunctionDef node."""

    def __init__(self, function_def: ast.FunctionDef):
        self._function_def = function_def

    def get_referenced_variable_names_in_parameter_defaults(self):
        """Get the list of variable names that are referenced in the function parameter defaults.

        i.e. Given the following function definition:

            def func(a, b=1, c=name, d=age):
                pass

        the returned value will be ['name', 'age'].
        """
        defaults = self._function_def.args.defaults
        return [n.id for n in defaults if isinstance(n, ast.Name)]
