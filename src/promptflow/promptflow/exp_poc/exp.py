from .file_clients.file_client_factory import FileClientFactory
from .utils.yaml_parser import YamlParser
from .contracts.entities import CachedExperimentConfig, ExperimentConfig
from .contracts.entities import GroupType, Step
from .contracts.entities import Experiment
from .contracts.entities import Variant

from datetime import datetime
from typing import Dict, Tuple
import threading
import contextvars


CACHE_EXPIRATION_SECONDS = 300

# cache mock
_cached_exp: Dict[str, CachedExperimentConfig] = {}
_cached_exp_lock = threading.Lock()


exp_variant = contextvars.ContextVar("exp_variant")
exp_ruid = contextvars.ContextVar("exp_ruid")
exp_variant.set(None)
exp_ruid.set(None)


# Load the experiment config (experiments.yaml) for assignment
# Requirement:
# 1. Support both local file and blob uri
# 2. Timely pull the latest content
# 3. Thread-safe, cache
def init(file_identifier: str):
    global _file_identifier
    _file_identifier = file_identifier

    if not _is_cache_valid(file_identifier):
        experiment_config = _load_config(file_identifier)
        if experiment_config:
            with _cached_exp_lock:
                _cached_exp[file_identifier] = CachedExperimentConfig(
                    experiment_config, datetime.now()
                )


# Get variant based on given randonmization unit ID and experiment name
# Extra Requirement: add extra columns into all the upcoming spans under
# same trace, including root span
# 1. "_exp.variants" column, the content format should be
#     "variant1A,variant2B", which includes assigned variant
#     name of all experiments
# 2. "_exp.ruid" column, the value is the input rand_unit_id
def get_variant(
    rand_unit_id: str,
    experiment_name: str
) -> Tuple[int, Variant]:
    bucket = _get_bucket(rand_unit_id)
    for exp in _cached_exp[_file_identifier].experiment_config.experiments:
        if exp.name == experiment_name:
            variant = _get_variant(exp, bucket)
            exp_variant.set(variant.name)
            exp_ruid.set(rand_unit_id)
            return bucket, variant
    return bucket, None


def _get_bucket(rand_unit_id: str) -> int:
    return sum(ord(c) for c in rand_unit_id) % 100


def _get_variant(experiment: Experiment, bucket: int) -> Variant:
    cur = 0
    default = None

    now = datetime.now()
    cur_step = None
    for step in experiment.steps:
        if _is_within_step(now, step):
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


def _is_within_step(timestamp: datetime, step: Step) -> bool:
    return timestamp >= step.start_time and timestamp < step.expire_time


def _is_cache_valid(file_identifier: str) -> bool:
    with _cached_exp_lock:
        if file_identifier not in _cached_exp:
            return False
        diff = datetime.now() - _cached_exp[file_identifier].last_updated
        return diff.total_seconds() < CACHE_EXPIRATION_SECONDS


def _load_config(file_identifier: str) -> ExperimentConfig:
    client = FileClientFactory.get_file_client(file_identifier)
    return YamlParser.load_to_dataclass(ExperimentConfig, client.load())
