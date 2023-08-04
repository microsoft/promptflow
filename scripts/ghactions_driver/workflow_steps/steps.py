from jinja2 import Environment, FileSystemLoader, Template


class Step:
    """
    StepType
    """

    Environment = None

    @staticmethod
    def init_jinja_loader() -> Environment:
        Step.Environment = Environment(loader=FileSystemLoader("./workflow_steps"))

    def set_workflow_name(self, name: str) -> None:
        self.workflow_name = name

    def get_workflow_step(self, step_file_name: str) -> Template:
        # virtual method for overide
        if Step.Environment is None:
            Step.init_jinja_loader()
        template = Step.Environment.get_template(step_file_name)
        return template;


class ReadmeStep:
    """
    Deal with readme replacements
    """

    def set_readme_name(self, name: str, comment=None, demo_command=None) -> None:
        self.readme_name = name
        self.replacements = {
            "comment": comment,
            "demo_command": demo_command,
        }

    def get_readme_step(self) -> str:
        # virtual method for overide
        comment_items = self.replacements['comment'].split("\n")
        comments = '\n'.join([f"# {item}" for item in comment_items])
        return f"{comments}\n{self.replacements['demo_command']}"


class CheckoutStep(Step, ReadmeStep):
    def __init__(self) -> None:
        super().set_workflow_name("Checkout repository")
        super().set_readme_name("Checkout repository")

    def get_workflow_step(self) -> str:
        template = super().get_workflow_step("step_checkout_repository.yml.jinja2")
        template.render({
            "step_name": self.workflow_name,
        })
    def get_readme_step(self) -> str:
        return "pip install -r requirements.txt"


class BashStep(Step, ReadmeStep):
    def __init__(self, command, demo_command=None, comment=None) -> None:
        super().set_workflow_name("Bash Execution")
        super().set_readme_name("Bash Execution")
        if demo_command is None:
            demo_command = command
        self.replacements = {
            "step_name": self.workflow_name,
            "command": command,
            "demo_command": demo_command,
            "comment": comment,
        }

    # def get_readme_step(self) -> str: default is fine
    def get_workflow_step(self) -> str:
        template = super().get_workflow_step("step_bash.yml.jinja2")
        return template.render(self.replacements)


class GenerateConfigStep(Step):
    def __init__(self) -> None:
        super().__init__("Generate config.json")

    def get_workflow_step(self) -> str:
        return (
            Step.get_workflow_step(self)
            + "\n"
            + " " * 8
            + "run: echo ${{ secrets.TEST_WORKSPACE_CONFIG_JSON }} > ${{ github.workspace }}/examples/config.json"
        )


class AzureLoginStep(Step):
    def __init__(self) -> None:
        super().__init__("Azure Login")

    def get_workflow_step(self) -> str:
        return (
            Step.get_workflow_step(self)
            + "\n"
            + " " * 8
            + "uses: azure/login@v1\n"
            + " " * 8
            + "with:\n"
            + " " * 10
            + "creds: ${{ secrets.AZURE_CREDENTIALS }}"
        )


class SetupPythonStep(Step):
    def __init__(self) -> None:
        super().__init__("Setup Python 3.9 environment")

    def get_workflow_step(self) -> str:
        return (
            Step.get_workflow_step(self)
            + "\n"
            + " " * 8
            + "uses: actions/setup-python@v4\n"
            + " " * 8
            + "with:\n"
            + " " * 10
            + 'python-version: "3.9"'
        )


class InstallDependenciesStep(Step):
    def __init__(self) -> None:
        super().__init__("Prepare requirements")

    def get_workflow_step(self) -> str:
        return (
            Step.get_workflow_step(self)
            + "\n"
            + " " * 8
            + "run: |\n"
            + " " * 10
            + "python -m pip install --upgrade pip\n"
            + " " * 10
            + "pip install -r ${{ github.workspace }}/examples/requirements.txt\n"
            + " " * 10
            + "pip install -r ${{ github.workspace }}/examples/dev_requirements.txt"
        )


class CreateAoaiConnectionStep(Step):
    def __init__(self) -> None:
        super().__init__("Create Aoai Connection")

    def get_workflow_step(self) -> str:
        return (
            Step.get_workflow_step(self)
            + "\n"
            + " " * 8
            + "run: pf connection create -f ${{ github.workspace }}/examples/connections/azure_openai.yml"
            + '--set api_key="${{ secrets.AOAI_API_KEY }}" api_base="${{ secrets.AOAI_API_ENDPOINT }}"'
        )


class RunTestStep(Step):
    def __init__(self, filename: str, filepath: str) -> None:
        super().__init__("Test Notebook")
        self.filename = filename
        self.filepath = filepath

    def get_workflow_step(self) -> str:
        return (
            Step.get_workflow_step(self)
            + "\n"
            + " " * 8
            + f"working-directory: {self.filepath}\n"
            + " " * 8
            + "run: |\n"
            + " " * 10
            + f"papermill -k python {self.filename}.ipynb {self.filename}.output.ipynb"
        )


class UploadArtifactStep(Step):
    def __init__(self, filepath: str) -> None:
        super().__init__("Upload artifact")
        self.filepath = filepath

    def get_workflow_step(self) -> str:
        """
        if: ${{ always() }}
        uses: actions/upload-artifact@v3
        with:
          name: artifact
          path: {self.filepath}
        """
        return (
            Step.get_workflow_step(self)
            + "\n"
            + " " * 8
            + "if: ${{ always() }}\n"
            + " " * 8
            + "uses: actions/upload-artifact@v3\n"
            + " " * 8
            + "with:\n"
            + " " * 10
            + "name: artifact\n"
            + " " * 10
            + f"path: {self.filepath}"
        )
