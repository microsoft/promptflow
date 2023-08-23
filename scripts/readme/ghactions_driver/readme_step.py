import subprocess
from pathlib import Path
import hashlib
from jinja2 import Environment, FileSystemLoader, Template
from .telemetry_obj import Telemetry


class Step:
    """
    StepType in workflow
    """

    Environment = None

    @staticmethod
    def init_jinja_loader() -> Environment:
        jinja_folder_path = (
            Path(ReadmeStepsManage.git_base_dir())
            / "scripts"
            / "readme"
            / "ghactions_driver"
            / "workflow_steps"
        )
        Step.Environment = Environment(
            loader=FileSystemLoader(jinja_folder_path.resolve())
        )

    def __init__(self, name: str) -> None:
        self.workflow_name = name

    def get_workflow_step(self) -> str:
        # virtual method for override
        return ""

    @staticmethod
    def get_workflow_template(step_file_name: str) -> Template:
        # virtual method for override
        if Step.Environment is None:
            Step.init_jinja_loader()
        template = Step.Environment.get_template(step_file_name)
        return template


class AzureLoginStep(Step):
    def __init__(self) -> None:
        Step.__init__(self, "Azure Login")

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_azure_login.yml.jinja2")
        return template.render(
            {
                "step_name": self.workflow_name,
            }
        )


class InstallDependenciesStep(Step):
    def __init__(self) -> None:
        Step.__init__(self, "Prepare requirements")

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_install_deps.yml.jinja2")
        return template.render(
            {
                "step_name": self.workflow_name,
                "working_dir": ReadmeSteps.working_dir,
            }
        )


class InstallDevDependenciesStep(Step):
    def __init__(self) -> None:
        Step.__init__(self, "Prepare dev requirements")

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_install_devdeps.yml.jinja2")
        return template.render(
            {
                "step_name": self.workflow_name,
                "working_dir": ReadmeSteps.working_dir,
            }
        )


class CreateAoaiFromYaml(Step):
    def __init__(self, yaml_name: str) -> None:
        Step.__init__(self, "Create AOAI Connection from YAML")
        self.yaml_name = yaml_name

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_yml_create_aoai.yml.jinja2")
        return template.render(
            {
                "step_name": self.workflow_name,
                "yaml_name": self.yaml_name,
            }
        )


class ExtractStepsAndRun(Step):
    def __init__(self) -> None:
        Step.__init__(self, f"Extract Steps {ReadmeSteps.readme_name}")

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_extract_steps_and_run.yml.jinja2")
        return template.render(
            {
                "step_name": self.workflow_name,
                "working_dir": ReadmeSteps.working_dir,
                "readme_name": ReadmeSteps.readme_name,
            }
        )


class ExtractStepsAndRunGPTFour(Step):
    def __init__(self) -> None:
        Step.__init__(self, f"Extract Steps {ReadmeSteps.readme_name}")

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template(
            "step_extract_steps_and_run_gpt4.yml.jinja2"
        )
        return template.render(
            {
                "step_name": self.workflow_name,
                "working_dir": ReadmeSteps.working_dir,
                "readme_name": ReadmeSteps.readme_name,
            }
        )


class CreateEnv(Step):
    def __init__(self) -> None:
        Step.__init__(self, "Refine .env file")

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_create_env.yml.jinja2")
        content = template.render(
            {"step_name": self.workflow_name, "working_dir": ReadmeSteps.working_dir}
        )
        return content


class CreateAoaiFromEnv(Step):
    def __init__(self, connection_name: str) -> None:
        Step.__init__(self, "Create AOAI Connection from ENV file")
        self.connection_name = connection_name

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_env_create_aoai.yml.jinja2")
        content = template.render(
            {
                "step_name": self.workflow_name,
                "working_dir": ReadmeSteps.working_dir,
                "connection_name": self.connection_name,
            }
        )
        return content


class CreateRunYaml(Step):
    def __init__(self) -> None:
        Step.__init__(self, "Create run.yml")

    def get_workflow_step(self) -> str:
        template = Step.get_workflow_template("step_create_run_yml.yml.jinja2")
        content = template.render(
            {"step_name": self.workflow_name, "working_dir": ReadmeSteps.working_dir}
        )
        return content


class ReadmeSteps:
    """
    Static class to record steps, to be filled in workflow templates and Readme
    """

    step_array = []  # Record steps
    readme_name = ""  # Record readme name
    working_dir = ""  # the working directory of flow, relative to git_base_dir
    template = ""  # Select a base template under workflow_templates folder
    workflow = ""  # Target workflow name to be generated

    @staticmethod
    def remember_step(step: Step) -> Step:
        ReadmeSteps.step_array.append(step)
        return step

    @staticmethod
    def get_length() -> int:
        return len(ReadmeSteps.step_array)

    # region steps
    @staticmethod
    def create_env() -> Step:
        return ReadmeSteps.remember_step(CreateEnv())

    @staticmethod
    def yml_create_aoai(yaml_name: str) -> Step:
        return ReadmeSteps.remember_step(CreateAoaiFromYaml(yaml_name=yaml_name))

    @staticmethod
    def env_create_aoai(connection_name: str) -> Step:
        return ReadmeSteps.remember_step(
            CreateAoaiFromEnv(connection_name=connection_name)
        )

    @staticmethod
    def azure_login() -> Step:
        return ReadmeSteps.remember_step(AzureLoginStep())

    @staticmethod
    def install_dependencies() -> Step:
        return ReadmeSteps.remember_step(InstallDependenciesStep())

    @staticmethod
    def install_dev_dependencies() -> Step:
        return ReadmeSteps.remember_step(InstallDevDependenciesStep())

    @staticmethod
    def create_run_yaml() -> Step:
        return ReadmeSteps.remember_step(CreateRunYaml())

    @staticmethod
    def extract_steps_and_run() -> Step:
        return ReadmeSteps.remember_step(ExtractStepsAndRun())

    @staticmethod
    def extract_steps_and_run_gpt_four() -> Step:
        return ReadmeSteps.remember_step(ExtractStepsAndRunGPTFour())

    # endregion steps

    @staticmethod
    def setup_target(
        working_dir: str, template: str, target: str, readme_name: str
    ) -> str:
        """
        Used at the very head of jinja template to indicate basic information
        """
        ReadmeSteps.working_dir = working_dir
        ReadmeSteps.template = template
        ReadmeSteps.workflow = target
        ReadmeSteps.step_array = []
        ReadmeSteps.readme_name = readme_name
        return ""

    @staticmethod
    def cleanup() -> None:
        ReadmeSteps.working_dir = ""
        ReadmeSteps.template = ""
        ReadmeSteps.workflow = ""
        ReadmeSteps.step_array = []


class ReadmeStepsManage:
    """
    # Static methods for manage all readme steps
    """

    repo_base_dir = ""

    @staticmethod
    def git_base_dir() -> str:
        """
        Get the base directory of the git repo
        """
        if ReadmeStepsManage.repo_base_dir == "":
            ReadmeStepsManage.repo_base_dir = (
                subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
                .decode("utf-8")
                .strip()
            )
        return ReadmeStepsManage.repo_base_dir

    @staticmethod
    def write_workflow(
        workflow_name: str, pipeline_name: str, output_telemetry=Telemetry()
    ) -> None:
        # Schedule notebooks at different times to reduce maximum quota usage.
        name_hash = int(hashlib.sha512(workflow_name.encode()).hexdigest(), 16)
        schedule_minute = name_hash % 60
        schedule_hour = (name_hash // 60) % 4 + 19  # 19-22 UTC

        if "tutorials" in workflow_name:
            path_filter = "[ examples/** ]"
        else:
            path_filter = f"[ {ReadmeSteps.working_dir}/** ]"
        replacements = {
            "steps": ReadmeSteps.step_array,
            "workflow_name": workflow_name,
            "ci_name": pipeline_name,
            "path_filter": path_filter,
            "crontab": f"{schedule_minute} {schedule_hour} * * *",
            "crontab_comment": f"Every day starting at {schedule_hour - 16}:{schedule_minute} BJT",
        }
        workflow_template_path = (
            Path(ReadmeStepsManage.git_base_dir())
            / "scripts"
            / "readme"
            / "ghactions_driver"
            / "workflow_templates"
        )
        template = Environment(
            loader=FileSystemLoader(workflow_template_path.resolve())
        ).get_template(ReadmeSteps.template)
        target_path = (
            Path(ReadmeStepsManage.git_base_dir())
            / ".github"
            / "workflows"
            / f"{workflow_name}.yml"
        )
        content = template.render(replacements)
        with open(target_path.resolve(), "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Write readme workflow: {target_path.resolve()}")
        output_telemetry.workflow_name = workflow_name
        output_telemetry.target_path = target_path
        output_telemetry.readme_folder = ReadmeSteps.working_dir
        output_telemetry.readme_name = ReadmeSteps.readme_name
