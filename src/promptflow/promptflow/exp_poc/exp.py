from promptflow._core.operation_context import OperationContext
from .file_clients.file_client_factory import FileClientFactory
from .utils.yaml_parser import YamlParser
from .contracts.entities import ExperimentConfig, ExperimentConfigCache, ExpContext
from .contracts.entities import GroupType, Step
from .contracts.entities import Experiment
from .contracts.entities import Variant

from datetime import datetime
from typing import Dict, Tuple
import threading
import contextvars


CACHE_EXPIRATION_SECONDS = 300


# Load the experiment config (experiments.yaml) for assignment
# Requirement:
# 1. Support both local file and blob uri
# 2. Timely pull the latest content
# 3. Thread-safe, cache
class Exp:

    # cache mock
    _cached_exp: Dict[str, ExperimentConfigCache] = {}
    _cached_exp_lock = threading.Lock()

    _context_vars_lock = threading.Lock()
    _exp_variants = contextvars.ContextVar("exp_variants")
    _exp_variants.set(None)
    _exp_ruid = contextvars.ContextVar("exp_ruid")
    _exp_ruid.set(None)

    _context_dict_lock = threading.Lock()
    _id_2_context: Dict[str, ExpContext] = {}

    def __init__(self, file_identifier: str):
        context_dict = OperationContext.get_instance()._get_tracking_info()

        print('----------------')
        print(context_dict)
        print('----------------')

        self._file_identifier = file_identifier

        if not Exp._is_cache_valid(file_identifier):
            Exp._update_cache(file_identifier)

    def get_variant(self, rand_unit_id: str, experiment_name: str) -> Tuple[int, Variant]:
        return Exp.get_variant_for_config(self._file_identifier, rand_unit_id, experiment_name)

    # Get variant based on given randonmization unit ID and experiment name
    # Extra Requirement: add extra columns into all the upcoming spans under
    # same trace, including root span
    # 1. "_exp.variants" column, the content format should be
    #     "variant1A,variant2B", which includes assigned variant
    #     name of all experiments
    # 2. "_exp.ruid" column, the value is the input rand_unit_id
    @staticmethod
    def get_variant_for_config(
        file_identifier: str,
        rand_unit_id: str,
        experiment_name: str
    ) -> Tuple[int, Variant]:
        bucket = Exp._get_bucket(rand_unit_id)
        for exp in Exp._cached_exp[file_identifier].experiment_config.experiments:
            if exp.name == experiment_name:
                variant = Exp._get_variant(exp, bucket)

                with Exp._context_vars_lock:
                    Exp._exp_ruid.set(rand_unit_id)
                    existing_variants = Exp._exp_variants.get()
                    if existing_variants:
                        variant_list = set(existing_variants.split(","))
                        if variant.name not in variant_list:
                            Exp._exp_variants.set(existing_variants + "," + variant.name)
                    else:
                        Exp._exp_variants.set(variant.name)
                return bucket, variant
        return bucket, None

    @staticmethod
    def map_context_with_id(id: str, context: ExpContext):
        with Exp._context_dict_lock:
            Exp._id_2_context[id] = context

    @staticmethod
    def get_context_by_id(id: str) -> ExpContext:
        if id not in Exp._id_2_context:
            return None
        with Exp._context_dict_lock:
            return Exp._id_2_context[id]

    @staticmethod
    def get_variants() -> str:
        return Exp._exp_variants.get()

    @staticmethod
    def get_ruid() -> str:
        return Exp._exp_ruid.get()

    @staticmethod
    def _update_cache(file_identifier: str):
        experiment_config = Exp._load_config(file_identifier)
        if experiment_config:
            with Exp._cached_exp_lock:
                Exp._cached_exp[file_identifier] = experiment_config
        threading.Timer(CACHE_EXPIRATION_SECONDS, Exp._update_cache, [file_identifier]).start()

    @staticmethod
    def _get_bucket(rand_unit_id: str) -> int:
        return sum(ord(c) for c in rand_unit_id) % 100

    @staticmethod
    def _get_variant(experiment: Experiment, bucket: int) -> Variant:
        cur = 0
        default = None

        now = datetime.now()
        cur_step = None
        for step in experiment.steps:
            if Exp._is_within_step(now, step):
                cur_step = step
                break
        if not cur_step:
            return default

        for variant in experiment.variants:
            if variant.type == GroupType.CONTROL:
                default = variant
            if (variant.type == GroupType.TREATMENT
                    and cur_step.traffic[variant.name] > 0):
                if bucket >= cur and bucket < cur + cur_step.traffic[variant.name]:
                    return variant
                cur += cur_step.traffic[variant.name]
        return default

    @staticmethod
    def _is_within_step(timestamp: datetime, step: Step) -> bool:
        return timestamp >= step.start_time and timestamp < step.expire_time

    @staticmethod
    def _is_cache_valid(file_identifier: str) -> bool:
        with Exp._cached_exp_lock:
            if file_identifier not in Exp._cached_exp:
                return False
            diff = datetime.now() - Exp._cached_exp[file_identifier].last_updated
            return diff.total_seconds() < CACHE_EXPIRATION_SECONDS

    @staticmethod
    def _load_config(file_identifier: str) -> ExperimentConfig:
        client = FileClientFactory.get_file_client(file_identifier)
        return YamlParser.load_to_dataclass(ExperimentConfig, client.load())
