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


def traverse_directory(
    root: str,
    files: List[str],
    source: str,
    prefix: str,
    ignore_file: IgnoreFile = IgnoreFile(),
) -> Iterable[Tuple[str, Union[str, Any]]]:
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
    :param source: Local path to project directory
    :type source: str
    :param prefix: Remote upload path for project directory (e.g. LocalUpload/<guid>/project_dir)
    :type prefix: str
    :param ignore_file: The .amlignore or .gitignore file in the project directory
    :type ignore_file: azure.ai.ml._utils._asset_utils.IgnoreFile
    :return: Zipped list of tuples representing the local path and remote destination path for each file
    :rtype: Iterable[Tuple[str, Union[str, Any]]]
    """
    # Normalize Windows paths. Note that path should be resolved first as long part will be converted to a shortcut in
    # Windows. For example, C:\Users\too-long-user-name\test will be converted to C:\Users\too-lo~1\test by default.
    # Refer to https://en.wikipedia.org/wiki/8.3_filename for more details.
    root = convert_windows_path_to_unix(Path(root).resolve())
    source = convert_windows_path_to_unix(Path(source).resolve())
    working_dir = convert_windows_path_to_unix(os.getcwd())
    project_dir = root[len(str(working_dir)) :] + "/"
    file_paths = [
        convert_windows_path_to_unix(os.path.join(root, name))
        for name in files
        if not ignore_file.is_file_excluded(os.path.join(root, name))
    ]  # get all files not excluded by the ignore file
    file_paths_including_links = {fp: None for fp in file_paths}

    for path in file_paths:
        target_prefix = ""
        symlink_prefix = ""

        # check for symlinks to get their true paths
        if os.path.islink(path):
            target_absolute_path = os.path.join(working_dir, os.readlink(path))
            target_prefix = "/".join([root, str(os.readlink(path))]).replace(project_dir, "/")

            # follow and add child links if the directory is a symlink
            if os.path.isdir(target_absolute_path):
                symlink_prefix = path.replace(root + "/", "")

                for r, _, f in os.walk(target_absolute_path, followlinks=True):
                    target_file_paths = {
                        os.path.join(r, name): symlink_prefix + os.path.join(r, name).replace(target_prefix, "")
                        for name in f
                    }  # for each symlink, store its target_path as key and symlink path as value
                    file_paths_including_links.update(target_file_paths)  # Add discovered symlinks to file paths list
            else:
                file_path_info = {
                    target_absolute_path: path.replace(root + "/", "")
                }  # for each symlink, store its target_path as key and symlink path as value
                file_paths_including_links.update(file_path_info)  # Add discovered symlinks to file paths list
            del file_paths_including_links[path]  # Remove original symlink entry now that detailed entry has been added

    file_paths = sorted(
        file_paths_including_links
    )  # sort files to keep consistent order in case of repeat upload comparisons
    dir_parts = [convert_windows_path_to_unix(os.path.relpath(root, source)) for _ in file_paths]
    dir_parts = ["" if dir_part == "." else dir_part + "/" for dir_part in dir_parts]
    blob_paths = []

    for dir_part, name in zip(dir_parts, file_paths):
        if file_paths_including_links.get(
            name
        ):  # for symlinks, use symlink name and structure in directory to create remote upload path
            blob_path = prefix + dir_part + file_paths_including_links.get(name)
        else:
            blob_path = prefix + dir_part + name.replace(root + "/", "")
        blob_paths.append(blob_path)

    return zip(file_paths, blob_paths)
