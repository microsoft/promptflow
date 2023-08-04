from jinja2 import Environment, FileSystemLoader
from workflow_steps.steps import *


class ReadmeSteps:
    """
    Static class for jinja replacements
    """

    step_array = []
    readme = ""
    template = ""
    workflow = ""

    @staticmethod
    def remember_step(step: ReadmeStep) -> ReadmeStep:
        ReadmeSteps.step_array.append(step)
        return step

    @staticmethod
    def get_length() -> int:
        return len(ReadmeSteps.step_array)

    @staticmethod
    def checkout_step() -> ReadmeStep:
        return ReadmeSteps.remember_step(CheckoutStep())

    @staticmethod
    def generate_config() -> ReadmeStep:
        return ReadmeSteps.remember_step(GenerateConfigStep())

    @staticmethod
    def azure_login() -> ReadmeStep:
        return ReadmeSteps.remember_step(AzureLoginStep())

    @staticmethod
    def setup_python() -> ReadmeStep:
        return ReadmeSteps.remember_step(SetupPythonStep())

    @staticmethod
    def install_dependencies() -> ReadmeStep:
        return ReadmeSteps.remember_step(InstallDependenciesStep())

    @staticmethod
    def bash(command, demo_command=None, comment=None) -> ReadmeStep:
        return ReadmeSteps.remember_step(BashStep(command, demo_command, comment))

    # @staticmethod
    # def run_tests() -> str:
    #    step = RunTestsStep()
    #    ReadmeSteps.remember_step(step)
    #    return step

    @staticmethod
    def setup_target(readme: str, template: str, target: str) -> str:
        ReadmeSteps.readme = readme
        ReadmeSteps.template = template
        ReadmeSteps.workflow = target
        ReadmeSteps.step_array = []
        return ""
    
    @staticmethod
    def cleanup() -> None:
        ReadmeSteps.readme = ''
        ReadmeSteps.template = ''
        ReadmeSteps.workflow = ''
        ReadmeSteps.step_array = []
        return ""

class ReadmeStepsManage:
    """
    # Static method for driver use.
    """

    @staticmethod
    def write_readme(content: str) -> None:
        with open(ReadmeSteps.readme, 'w') as f:
            f.write(content)
    
    @staticmethod
    def write_workflow() -> None:
        replacements = {
            "steps": ReadmeSteps.step_array,
            "workflow_name": "Yes",
        }
        template = Environment(loader=FileSystemLoader("./workflow_templates")).get_template(
            ReadmeSteps.template
        )
        content = template.render(replacements)
        with open(ReadmeSteps.workflow, 'w') as f:
            f.write(content)
            
