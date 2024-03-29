import os
from .file_clients.file_client_factory import FileClientFactory
from .utils.yaml_parser import YamlParser
from .contracts.entities import ExperimentConfig, ExperimentConfigCache
from .contracts.entities import GroupType, Step
from .contracts.entities import Experiment
from .contracts.entities import Variant

from datetime import datetime
from typing import Dict, List
import threading
import contextvars


CACHE_EXPIRATION_SECONDS = 300


# Load the experiment config (experiments.yaml) for assignment
# Requirement:
# 1. Support both local file and blob uri
# 2. Timely pull the latest content
# 3. Thread-safe, cache
class Exp:

    _exp_config_file_identifier: str = None

    # cache for experiment config
    _exp_config_cache: ExperimentConfigCache = None
    _exp_config_cache_lock = threading.Lock()

    # context of ruid
    _exp_ruid = contextvars.ContextVar("exp_ruid")
    _exp_ruid.set(None)

    # kvs for ruid to (experiment name -> variant)
    _ruid_to_variants: Dict[str, Dict[str, Variant]] = {}
    _ruid_to_variants_lock = threading.Lock()

    # kvs for tracing/span id to ruid
    _trace_id_to_ruid: Dict[str, str] = {}
    _trace_id_to_ruid_lock = threading.Lock()

    @staticmethod
    def init(file_identifier: str):
        Exp._exp_config_file_identifier = file_identifier

        if not Exp._is_cache_valid():
            if Exp._is_serving_mode():
                Exp._update_cache_passively()
            else:
                Exp._update_cache_actively()

    # Get variant based on given randonmization unit ID and experiment name
    # Extra Requirement: add extra columns into all the upcoming spans under
    # same trace, including root span
    # 1. "_exp.variants" column, the content format should be
    #     "variant1A,variant2B", which includes assigned variant
    #     name of all experiments
    # 2. "_exp.ruid" column, the value is the input rand_unit_id
    @staticmethod
    def assign_variant(
        ruid: str,
        experiment_name: str
    ) -> Variant:
        if not Exp._exp_config_file_identifier:
            return Variant()

        if not Exp._is_serving_mode():
            Exp._update_cache_actively()
        if Exp._exp_config_cache is None:
            return None

        Exp._exp_ruid.set(ruid)
        bucket = Exp._get_bucket(ruid)
        for exp in Exp._exp_config_cache.experiment_config.experiments:
            if exp.name == experiment_name:
                variant = Exp._get_variant(exp, bucket)

                with Exp._ruid_to_variants_lock:
                    if ruid not in Exp._ruid_to_variants:
                        Exp._ruid_to_variants[ruid] = {}
                    Exp._ruid_to_variants[ruid][experiment_name] = variant
                return variant
        return None

    @staticmethod
    def get_variable(experiment_name: str, variable_name: str, default: object):
        if not Exp._exp_config_file_identifier:
            return default

        ruid = Exp.get_ruid()
        variant = None
        if ruid and ruid in Exp._ruid_to_variants:
            variants = Exp._ruid_to_variants[ruid]
            if experiment_name in variants:
                variant = variants[experiment_name]
        if variable_name in variant.variables:
            return variant.variables[variable_name]
        return default

    @staticmethod
    def map_ruid_with_trace_id(ruid: str, trace_id: str):
        with Exp._trace_id_to_ruid_lock:
            Exp._trace_id_to_ruid[trace_id] = ruid

    @staticmethod
    def get_ruid_by_trace_id(trace_id: str) -> str:
        if trace_id not in Exp._trace_id_to_ruid:
            return None
        return Exp._trace_id_to_ruid[trace_id]

    @staticmethod
    def get_variant_names_by_trace_id(trace_id: str) -> List[str]:
        if trace_id not in Exp._trace_id_to_ruid:
            return None
        ruid = Exp._trace_id_to_ruid[trace_id]
        if ruid not in Exp._ruid_to_variants:
            return None
        return [variant.name for variant in Exp._ruid_to_variants[ruid].values()]

    @staticmethod
    def get_variant_names_from_context() -> List[str]:
        ruid = Exp.get_ruid()
        if not ruid or (ruid not in Exp._ruid_to_variants):
            return None
        return [variant.name for variant in Exp._ruid_to_variants[ruid].values()]

    @staticmethod
    def get_ruid() -> str:
        try:
            return Exp._exp_ruid.get()
        except LookupError:
            return None

    @staticmethod
    def _update_cache_actively():
        if not Exp._is_cache_valid():
            Exp._do_update_cache()

    @staticmethod
    def _update_cache_passively():
        Exp._do_update_cache()
        threading.Timer(CACHE_EXPIRATION_SECONDS, Exp._update_cache_passively).start()

    @staticmethod
    def _do_update_cache():
        if not Exp._exp_config_file_identifier:
            return

        experiment_config = Exp._load_config(Exp._exp_config_file_identifier)
        if experiment_config:
            with Exp._exp_config_cache_lock:
                Exp._exp_config_cache = ExperimentConfigCache(
                    file_identifier=Exp._exp_config_file_identifier,
                    experiment_config=experiment_config,
                    last_updated=datetime.now()
                )

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
    def _is_cache_valid() -> bool:
        with Exp._exp_config_cache_lock:
            if Exp._exp_config_cache is None:
                return False
            diff = datetime.now() - Exp._exp_config_cache.last_updated
            return diff.total_seconds() < CACHE_EXPIRATION_SECONDS

    @staticmethod
    def _load_config(file_identifier: str) -> ExperimentConfig:
        client = FileClientFactory.get_file_client(file_identifier)
        return YamlParser.load_to_dataclass(ExperimentConfig, client.load())

    @staticmethod
    def _is_serving_mode() -> bool:
        run_mode = os.environ.get("PROMPTFLOW_RUN_MODE")
        return run_mode and run_mode.lower() == "serving"
