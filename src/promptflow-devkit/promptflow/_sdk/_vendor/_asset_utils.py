# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
"""
This file code has been vendored from azure-ai-ml repo.
Please do not edit it, unless really necessary
"""

# region Diff-imports
import os
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, List, Optional, Tuple, Union

from ._pathspec import GitWildMatchPattern, normalize_file

GIT_IGNORE_FILE_NAME = ".gitignore"
AML_IGNORE_FILE_NAME = ".amlignore"


def convert_windows_path_to_unix(path: Union[str, os.PathLike]) -> str:
    return PureWindowsPath(path).as_posix()


# endregion


class IgnoreFile(object):
    def __init__(self, file_path: Optional[Union[str, Path]] = None):
        """Base class for handling .gitignore and .amlignore files.

        :param file_path: Relative path, or absolute path to the ignore file.
        """
        path = Path(file_path).resolve() if file_path else None
        self._path = path
        self._path_spec = None

    def exists(self) -> bool:
        """Checks if ignore file exists."""
        return self._file_exists()

    def _file_exists(self) -> bool:
        return self._path and self._path.exists()

    @property
    def base_path(self) -> Path:
        return self._path.parent

    def _get_ignore_list(self) -> List[str]:
        """Get ignore list from ignore file contents."""
        if not self.exists():
            return []
        if self._file_exists():
            with open(self._path, "r") as fh:
                return [line.rstrip() for line in fh if line]
        return []

    def _create_pathspec(self) -> List[GitWildMatchPattern]:
        """Creates path specification based on ignore list."""
        return [GitWildMatchPattern(ignore) for ignore in self._get_ignore_list()]

    def _get_rel_path(self, file_path: Union[str, Path]) -> Optional[str]:
        """Get relative path of given file_path."""
        file_path = Path(file_path).absolute()
        try:
            # use os.path.relpath instead of Path.relative_to in case file_path is not a child of self.base_path
            return os.path.relpath(file_path, self.base_path)
        except ValueError:
            # 2 paths are on different drives
            return None

    def is_file_excluded(self, file_path: Union[str, Path]) -> bool:
        """Checks if given file_path is excluded.

        :param file_path: File path to be checked against ignore file specifications
        """
        # TODO: current design of ignore file can't distinguish between files and directories of the same name
        if self._path_spec is None:
            self._path_spec = self._create_pathspec()
        if not self._path_spec:
            return False
        file_path = self._get_rel_path(file_path)
        if file_path is None:
            return True

        norm_file = normalize_file(file_path)
        matched = False
        for pattern in self._path_spec:
            if pattern.include is not None:
                if pattern.match_file(norm_file) is not None:
                    matched = pattern.include

        return matched

    @property
    def path(self) -> Union[Path, str]:
        return self._path


class AmlIgnoreFile(IgnoreFile):
    def __init__(self, directory_path: Union[Path, str]):
        file_path = Path(directory_path).joinpath(AML_IGNORE_FILE_NAME)
        super(AmlIgnoreFile, self).__init__(file_path)


class GitIgnoreFile(IgnoreFile):
    def __init__(self, directory_path: Union[Path, str]):
        file_path = Path(directory_path).joinpath(GIT_IGNORE_FILE_NAME)
        super(GitIgnoreFile, self).__init__(file_path)


def get_ignore_file(directory_path: Union[Path, str]) -> Optional[IgnoreFile]:
    """Finds and returns IgnoreFile object based on ignore file found in directory_path.

    .amlignore takes precedence over .gitignore and if no file is found, an empty
    IgnoreFile object will be returned.

    The ignore file must be in the root directory.

    :param directory_path: Path to the (root) directory where ignore file is located
    """
    aml_ignore = AmlIgnoreFile(directory_path)
    git_ignore = GitIgnoreFile(directory_path)

    if aml_ignore.exists():
        return aml_ignore
    if git_ignore.exists():
        return git_ignore
    return IgnoreFile()


def get_upload_files_from_folder(
    path: Union[str, Path], *, prefix: str = "", ignore_file: IgnoreFile = IgnoreFile()
) -> List[Tuple[str, str]]:
    """Enumerate all files in the given directory and compose paths for them to be uploaded to in the remote storage.

    :param path: Path to the directory to be uploaded
    :type path: str
    :param prefix: Prefix for remote storage path
    :type prefix: str
    :param ignore_file: Ignore file object
    :type ignore_file: IgnoreFile
    :return: List of tuples of (local path, remote path)
    :rtype: list
    """
    path = Path(path)
    upload_paths = []
    for root, _, files in os.walk(path, followlinks=True):
        upload_paths += list(
            traverse_directory(
                root,
                files,
                prefix=Path(prefix).joinpath(Path(root).relative_to(path)).as_posix(),
                ignore_file=ignore_file,
            )
        )
    return upload_paths


def traverse_directory(
    root: str,
    files: List[str],
    *,
    prefix: str,
    ignore_file: IgnoreFile = IgnoreFile(),
    # keep this for backward compatibility
    **kwargs: Any,
) -> Iterable[Tuple[str, str]]:
    """Enumerate all files in the given directory and compose paths for them to be uploaded to in the remote storage.
    e.g.

    [/mnt/c/Users/dipeck/upload_files/my_file1.txt,
    /mnt/c/Users/dipeck/upload_files/my_file2.txt] -->

        [(/mnt/c/Users/dipeck/upload_files/my_file1.txt, LocalUpload/<guid>/upload_files/my_file1.txt),
        (/mnt/c/Users/dipeck/upload_files/my_file2.txt, LocalUpload/<guid>/upload_files/my_file2.txt))]

    :param root: Root directory path
    :type root: str
    :param files: List of all file paths in the directory
    :type files: List[str]
    :param prefix: Remote upload path for project directory (e.g. LocalUpload/<guid>/project_dir)
    :type prefix: str
    :param ignore_file: The .amlignore or .gitignore file in the project directory
    :type ignore_file: azure.ai.ml._utils._asset_utils.IgnoreFile
    :return: Zipped list of tuples representing the local path and remote destination path for each file
    :rtype: Iterable[Tuple[str, str]]
    """
    # Normalize Windows paths. Note that path should be resolved first as long part will be converted to a shortcut in
    # Windows. For example, C:\Users\too-long-user-name\test will be converted to C:\Users\too-lo~1\test by default.
    # Refer to https://en.wikipedia.org/wiki/8.3_filename for more details.
    root = Path(root).resolve().absolute()

    # filter out files excluded by the ignore file
    # TODO: inner ignore file won't take effect. A merged IgnoreFile need to be generated in code resolution.
    origin_file_paths = [
        root.joinpath(filename)
        for filename in files
        if not ignore_file.is_file_excluded(root.joinpath(filename).as_posix())
    ]

    result = []
    for origin_file_path in origin_file_paths:
        relative_path = origin_file_path.relative_to(root)
        result.append((_resolve_path(origin_file_path).as_posix(), Path(prefix).joinpath(relative_path).as_posix()))
    return result


def _resolve_path(path: Path) -> Path:
    if not path.is_symlink():
        return path

    link_path = path.resolve()
    if not link_path.is_absolute():
        link_path = path.parent.joinpath(link_path).resolve()
    return _resolve_path(link_path)
