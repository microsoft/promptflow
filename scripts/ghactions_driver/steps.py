from .driver import Step


class CheckoutStep(Step):
    def __init__(self) -> None:
        super().__init__("Checkout repository")

    def get_step(self) -> str:
        return Step.get_step(self) + "\n" + " " * 8 + "uses: actions/checkout@v3"


class GenerateConfigStep(Step):
    def __init__(self) -> None:
        super().__init__("Generate config.json")

    def get_step(self) -> str:
        return (
            Step.get_step(self)
            + "\n"
            + " " * 8
            + "run: echo ${{ secrets.TEST_WORKSPACE_CONFIG_JSON }} > ${{ github.workspace }}/examples/config.json"
        )


class AzureLoginStep(Step):
    def __init__(self) -> None:
        super().__init__("Azure Login")

    def get_step(self) -> str:
        return (
            Step.get_step(self)
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

    def get_step(self) -> str:
        return (
            Step.get_step(self)
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

    def get_step(self) -> str:
        return (
            Step.get_step(self)
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

    def get_step(self) -> str:
        return (
            Step.get_step(self)
            + "\n"
            + " " * 8
            + 'run: pf connection create -f ${{ github.workspace }}/examples/connections/azure_openai.yml --set api_key="${{ secrets.AOAI_API_KEY }}" api_base="${{ secrets.AOAI_API_ENDPOINT }}"'
        )


class RunTestStep(Step):
    def __init__(self, filename: str, filepath: str) -> None:
        super().__init__("Test Notebook")
        self.filename = filename
        self.filepath = filepath

    def get_step(self) -> str:
        return (
            Step.get_step(self)
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

    def get_step(self) -> str:
        return (
            Step.get_step(self)
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
