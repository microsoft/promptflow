from jinja2 import Environment, FileSystemLoader, Template
import subprocess
from pathlib import Path


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
        if self.replacements['comment'] is not None:
            comment_items = self.replacements['comment'].split("\n")
            comments = '\n'.join([f"# {item}" for item in comment_items])
            return f"{comments}\n{self.replacements['demo_command']}"
        else:
            return f"{self.replacements['demo_command']}"

class Step:
    """
    StepType
    """

    Environment = None

    @staticmethod
    def init_jinja_loader() -> Environment:
        jinja_folderpath = Path(ReadmeStepsManage.git_base_dir()) / "scripts" / "ghactions_driver" / "workflow_steps"
        Step.Environment = Environment(loader=FileSystemLoader(jinja_folderpath.resolve()))

    def set_workflow_name(self, name: str) -> None:
        self.workflow_name = name
    
    def get_workflow_step(self) -> str:
        # virtual method for overide
        return ""

    @staticmethod
    def get_workflow_template(step_file_name: str) -> Template:
        # virtual method for overide
        if Step.Environment is None:
            Step.init_jinja_loader()
        template = Step.Environment.get_template(step_file_name)
        return template

class BashStep(Step, ReadmeStep):
    def __init__(self, command, demo_command=None, comment=None, no_output=False) -> None:
        super().set_workflow_name("Bash Execution")
        super().set_readme_name("Bash Execution")
        if demo_command is None:
            demo_command = command
        self.replacements = {
            "step_name": self.workflow_name,
            "command": command,
            "demo_command": demo_command,
            "comment": comment,
            "working_dir": ReadmeSteps.working_dir,
        }
        self.no_output = no_output

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_bash.yml.jinja2")
        content = template.render(self.replacements)
        return content
    
    def get_readme_step(self) -> str:
        if self.no_output:
            return ""
        return super().get_readme_step()


class AzureLoginStep(Step, ReadmeStep):
    def __init__(self) -> None:
        super().set_workflow_name("Azure Login")
        super().set_readme_name("Azure Login")

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_azure_login.yml.jinja2")
        template.render({
            "step_name": self.workflow_name,
        })
    def get_readme_step(self) -> str:
        return ""

class InstallDependenciesStep(Step, ReadmeStep):
    def __init__(self) -> None:
        super().set_workflow_name("Prepare requirements")
        super().set_readme_name("Prepare requirements")

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_install_deps.yml.jinja2")
        return template.render({
            "step_name": self.workflow_name,
            "working_dir": ReadmeSteps.working_dir,
        })
    def get_readme_step(self) -> str:
        return "pip install -r requirements.txt"

class InstallDevDependenciesStep(Step, ReadmeStep):
    def __init__(self) -> None:
        super().set_workflow_name("Prepare dev requirements")
        super().set_readme_name("Prepare dev requirements")

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_install_devdeps.yml.jinja2")
        return template.render({
            "step_name": self.workflow_name,
            "working_dir": ReadmeSteps.working_dir,
        })
    def get_readme_step(self) -> str:
        return ""
    
class CreateAoaiFromYaml(Step, ReadmeStep):
    def __init__(self, yaml_name: str) -> None:
        super().set_workflow_name("Create AOAI Connection from YAML")
        super().set_readme_name("Create AOAI Connection from YAML")
        self.yaml_name = yaml_name
    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_yml_create_aoai.yml.jinja2")
        return template.render({
            "step_name": self.workflow_name,
            "working_dir": ReadmeSteps.working_dir,
            "yaml_name": self.yaml_name,
        })
    def get_readme_step(self) -> str:
        return "pf connection create --file azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>"

class CreateEnv(Step, ReadmeStep):
    def __init__(self) -> None:
        super().set_workflow_name("Create Python Environment")
        super().set_readme_name("Create Python Environment")
    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_create_env.yml.jinja2")
        content = template.render({
            "step_name": self.workflow_name,
            "working_dir": ReadmeSteps.working_dir
        })
        return content
    def get_readme_step(self) -> str:
        return ""

class CreateRunYaml(Step, ReadmeStep):
    def __init__(self) -> None:
        super().set_workflow_name("Create run.yml")
        super().set_readme_name("Create run.yml")
    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_create_run_yml.yml.jinja2")
        content = template.render({
            "step_name": self.workflow_name,
            "working_dir": ReadmeSteps.working_dir
        })
        return content
    def get_readme_step(self) -> str:
        return ""

class ReadmeSteps:
    """
    Static class for jinja replacements
    """

    step_array = []
    working_dir = ""
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
    def create_env() -> ReadmeStep:
        return ReadmeSteps.remember_step(CreateEnv())

    @staticmethod
    def yml_create_aoai(yaml_name: str) -> ReadmeStep:
        return ReadmeSteps.remember_step(CreateAoaiFromYaml(yaml_name=yaml_name))

    @staticmethod
    def azure_login() -> ReadmeStep:
        return ReadmeSteps.remember_step(AzureLoginStep())

    @staticmethod
    def install_dependencies() -> ReadmeStep:
        return ReadmeSteps.remember_step(InstallDependenciesStep())
    
    @staticmethod
    def install_dev_dependencies() -> ReadmeStep:
        return ReadmeSteps.remember_step(InstallDevDependenciesStep())

    @staticmethod
    def bash(command, demo_command=None, comment=None, no_output=False) -> ReadmeStep:
        return ReadmeSteps.remember_step(BashStep(command, demo_command, comment, no_output=no_output))
    
    @staticmethod
    def create_run_yaml() -> ReadmeStep:
        return ReadmeSteps.remember_step(CreateRunYaml())

    # @staticmethod
    # def run_tests() -> str:
    #    step = RunTestsStep()
    #    ReadmeSteps.remember_step(step)
    #    return step

    @staticmethod
    def setup_target(working_dir: str, readme: str, template: str, target: str) -> str:
        ReadmeSteps.working_dir = working_dir
        ReadmeSteps.readme = readme
        ReadmeSteps.template = template
        ReadmeSteps.workflow = target
        ReadmeSteps.step_array = []
        return ""
    
    @staticmethod
    def cleanup() -> None:
        ReadmeSteps.working_dir = ''
        ReadmeSteps.readme = ''
        ReadmeSteps.template = ''
        ReadmeSteps.workflow = ''
        ReadmeSteps.step_array = []
        return ""

class ReadmeStepsManage:
    """
    # Static method for driver use.
    """
    repo_base_dir = ""
    @staticmethod
    def git_base_dir() -> str:
        """
        Get the base directory of the git repo
        """
        if ReadmeStepsManage.repo_base_dir == "":
            repo_base_dir = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode("utf-8").strip()
        return repo_base_dir

    @staticmethod
    def write_readme(content: str) -> None:
        filename = Path(ReadmeStepsManage.git_base_dir()) / ReadmeSteps.working_dir / ReadmeSteps.readme
        with open(filename.resolve(), 'w', encoding='utf-8') as f:
            f.write(content)
    
    @staticmethod
    def write_workflow() -> None:
        workflow_name = "Yes"
        replacements = {
            "steps": ReadmeSteps.step_array,
            "workflow_name": workflow_name,
            "name": workflow_name,
        }
        template = Environment(loader=FileSystemLoader("./workflow_templates")).get_template(
            ReadmeSteps.template
        )
        Path(ReadmeStepsManage.git_base_dir()) / ".github" / "workflows" / f"{workflow_name}.yml"
        content = template.render(replacements)
        with open(ReadmeSteps.workflow, 'w') as f:
            f.write(content)
            
