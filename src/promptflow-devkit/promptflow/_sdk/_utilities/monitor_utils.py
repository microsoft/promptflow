import abc
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import List

from promptflow._sdk._constants import DEFAULT_ENCODING


class MonitorTarget(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def get_key(self) -> str:
        pass

    def get_children(self) -> List["MonitorTarget"]:
        return []

    @abc.abstractmethod
    def _update_stat(self, key: str, cache: dict) -> bool:
        pass

    def update_cache(self, cache: dict, visited=None) -> bool:
        if visited is None:
            check_visited = True
            visited = set()
        else:
            check_visited = False

        updated = False
        for target in self.get_children():
            updated = target.update_cache(cache, visited) or updated

        key = self.get_key()
        visited.add(key)
        updated = self._update_stat(key, cache) or updated

        if check_visited:
            missed_items = set(cache.keys()) - visited
            if missed_items:
                for missed_item in missed_items:
                    del cache[missed_item]
                updated = True
        return updated


class DirectoryModificationMonitorTarget(MonitorTarget):
    """Monitor target for a specific directory.
    Will monitor add/remove/modify events for files in the directory but won't monitor the directories, which will be
    when directory tree is changed like a new subdirectory is added.

    :param target: Path to the directory
    :param relative_root_ignores: List of relative paths to ignore from the root directory;
        only 1 level deep is supported for now.
    """

    def __init__(self, target: Path, relative_root_ignores: List[str] = None):
        super().__init__()
        self._target = target.resolve().absolute()
        self._ignores = [(self._target / ignore).as_posix() for ignore in (relative_root_ignores or [])]

    def get_key(self) -> str:
        return self._target.as_posix()

    def _update_stat(self, key: str, cache: dict) -> bool:
        # directory itself is not monitored
        return False

    def get_children(self) -> List["MonitorTarget"]:
        for base, dirs, files in os.walk(self._target):
            base = Path(base)
            if base.as_posix() in self._ignores or any(
                base.as_posix().startswith(ignore + "/") for ignore in self._ignores
            ):
                continue
            yield from [FileModificationMonitorTarget(base / f) for f in files]


class FileModificationMonitorTarget(MonitorTarget):
    """Monitor target for a specific file. Note that it assumes that the file exists.

    :param target: Path to the file
    """

    def __init__(self, target: Path):
        super().__init__()
        self._target = target.absolute()

    def get_key(self) -> str:
        return self._target.as_posix()

    def _update_stat(self, key: str, cache: dict) -> bool:
        stat = self._target.stat().st_mtime
        if key not in cache or cache[key] != stat:
            cache[key] = stat
            return True
        return False


class JsonContentMonitorTarget(MonitorTarget):
    """Monitor target for a specific child node in a JSON file content.

    :param target: Path to the JSON file
    :param node_path: List of keys to traverse the JSON content to the target node
    """

    def __init__(self, target: Path, node_path: List[str]):
        super().__init__()
        self._target = target.absolute()
        self._keys = node_path

    def get_key(self) -> str:
        return self._target.as_posix() + "*" + "*".join(self._keys)

    def _update_stat(self, target_key: str, cache: dict) -> bool:
        modified_time = self._target.stat().st_mtime if self._target.exists() else None
        # no modification, no need to check content
        if target_key in cache and cache[target_key][0] == modified_time:
            return False

        try:
            content = json.loads(self._target.read_text(encoding=DEFAULT_ENCODING))
        except (json.JSONDecodeError, FileNotFoundError):
            content = None

        for k in self._keys:
            if content is not None:
                content = content.get(k, None)
        if target_key in cache and cache[target_key][1] == content:
            return False
        cache[target_key] = (modified_time, content)
        return True


class Monitor:
    """Monitor class to monitor multiple MonitorTargets.

    :param targets: List of MonitorTarget instances to monitor
    :param target_callback: Callback function to be called when any MonitorTarget is updated
    :param target_callback_kwargs: Keyword arguments for target_callback
    :param call_in_first_run: Whether to always call target_callback in the first run
    :param inject_last_callback_result: Whether to inject last callback result to target_callback
    """

    def __init__(
        self,
        targets: List[MonitorTarget],
        target_callback=None,
        target_callback_kwargs=None,
        call_in_first_run: bool = True,
        inject_last_callback_result: bool = False,
        extra_logic_in_loop=None,
    ):
        self._monitor_targets = targets
        # each monitor target has its own cache to check visited items
        self._caches = defaultdict(dict)

        self._target_callback = target_callback
        self._target_callback_kwargs = target_callback_kwargs or {}
        self._call_in_first_run = call_in_first_run

        self._last_callback_result = None
        self._inject_last_callback_result = inject_last_callback_result

        self._extra_logic_in_loop = extra_logic_in_loop

    @property
    def last_callback_result(self):
        return self._last_callback_result

    def start_monitor(self, interval=0.1):
        """Start monitoring the targets.

        :param interval: Interval in seconds to check the targets
        """
        while True:
            if self._extra_logic_in_loop:
                self._extra_logic_in_loop()

            updated = False
            for monitor_target in self._monitor_targets:
                # force update cache
                updated = monitor_target.update_cache(self._caches[id(monitor_target)]) or updated
            if updated or self._call_in_first_run:
                if callable(self._target_callback):
                    if self._inject_last_callback_result:
                        self._last_callback_result = self._target_callback(
                            last_result=self._last_callback_result, **self._target_callback_kwargs
                        )
                    else:
                        self._target_callback(**self._target_callback_kwargs)
                    self._call_in_first_run = False
            time.sleep(interval)
