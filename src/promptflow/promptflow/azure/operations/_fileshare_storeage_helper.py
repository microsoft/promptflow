# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
from collections import defaultdict
from functools import cached_property
from multiprocessing import Lock
from pathlib import Path
from typing import Any, Dict, Optional

from azure.ai.ml._artifacts._fileshare_storage_helper import FileStorageClient
from azure.ai.ml._utils._asset_utils import (
    DirectoryUploadProgressBar,
    FileUploadProgressBar,
    IgnoreFile,
    get_directory_size,
)
from azure.core.exceptions import ResourceExistsError
from azure.storage.fileshare import DirectoryProperties, ShareDirectoryClient

from promptflow._sdk._vendor import get_upload_files_from_folder
from promptflow.azure._constants._flow import PROMPTFLOW_FILE_SHARE_DIR
from promptflow.azure._utils.gerneral import get_user_alias_from_credential

uploading_lock = defaultdict(Lock)


class FlowFileStorageClient(FileStorageClient):
    def __init__(self, credential: str, file_share_name: str, account_url: str, azure_cred):
        super().__init__(credential=credential, file_share_name=file_share_name, account_url=account_url)
        try:
            user_alias = get_user_alias_from_credential(azure_cred)
        except Exception:
            # fall back to unknown user when failed to get credential.
            user_alias = "unknown_user"
        self._user_alias = user_alias

        # TODO: update this after we finalize the design for flow file storage client
        # create user folder if not exist
        for directory_path in ["Users", f"Users/{user_alias}", f"Users/{user_alias}/{PROMPTFLOW_FILE_SHARE_DIR}"]:
            self.directory_client = ShareDirectoryClient(
                account_url=account_url,
                credential=credential,
                share_name=file_share_name,
                directory_path=directory_path,
            )

            # try to create user folder if not exist
            try:
                self.directory_client.create_directory()
            except ResourceExistsError:
                pass

    @cached_property
    def file_share_prefix(self) -> str:
        return f"Users/{self._user_alias}/{PROMPTFLOW_FILE_SHARE_DIR}"

    def upload(
        self,
        source: str,
        name: str,
        version: str,
        ignore_file: IgnoreFile = IgnoreFile(None),
        asset_hash: Optional[str] = None,
        show_progress: bool = True,
    ) -> Dict[str, str]:
        """Upload a file or directory to a path inside the file system."""
        source_name = Path(source).name
        dest = asset_hash

        # truncate path longer than 50 chars for terminal display
        if show_progress and len(source_name) >= 50:
            formatted_path = "{:.47}".format(source_name) + "..."
        else:
            formatted_path = source_name
        msg = f"Uploading {formatted_path}"

        # lock to prevent concurrent uploading of the same file or directory
        with uploading_lock[self.directory_client.directory_path + "/" + dest]:
            # start upload
            if os.path.isdir(source):
                subdir = self.directory_client.get_subdirectory_client(dest)
                if not subdir.exists():
                    # directory is uploaded based on asset hash for now, so skip uploading if subdir exists
                    self.upload_dir(
                        source,
                        dest,
                        msg=msg,
                        show_progress=show_progress,
                        ignore_file=ignore_file,
                    )
            else:
                self.upload_file(source, dest=dest, msg=msg, show_progress=show_progress)

        artifact_info = {"remote path": dest, "name": name, "version": version}

        return artifact_info

    def upload_file(
        self,
        source: str,
        dest: str,
        show_progress: Optional[bool] = None,
        msg: Optional[str] = None,
        in_directory: bool = False,
        subdirectory_client: Optional[ShareDirectoryClient] = None,
        callback: Optional[Any] = None,
    ) -> None:
        """ " Upload a single file to a path inside the file system
        directory."""
        validate_content = os.stat(source).st_size > 0  # don't do checksum for empty files
        # relative path from root
        relative_path = Path(subdirectory_client.directory_path).relative_to(self.directory_client.directory_path)
        dest = Path(dest).relative_to(relative_path).as_posix()
        if "/" in dest:
            # dest is a folder, need to switch subdirectory client
            dest_dir, dest = dest.rsplit("/", 1)
            subdirectory_client = subdirectory_client.get_subdirectory_client(dest_dir)
        with open(source, "rb") as data:
            if in_directory:
                file_name = dest.rsplit("/")[-1]
                if show_progress:
                    subdirectory_client.upload_file(
                        file_name=file_name,
                        data=data,
                        validate_content=validate_content,
                        raw_response_hook=callback,
                    )
                else:
                    subdirectory_client.upload_file(
                        file_name=file_name,
                        data=data,
                        validate_content=validate_content,
                    )
            else:
                if show_progress:
                    with FileUploadProgressBar(msg=msg) as progress_bar:
                        self.directory_client.upload_file(
                            file_name=dest,
                            data=data,
                            validate_content=validate_content,
                            raw_response_hook=progress_bar.update_to,
                        )
                else:
                    self.directory_client.upload_file(file_name=dest, data=data, validate_content=validate_content)
        self.uploaded_file_count = self.uploaded_file_count + 1

    def upload_dir(
        self,
        source: str,
        dest: str,
        msg: str,
        show_progress: bool,
        ignore_file: IgnoreFile,
    ) -> None:
        """Upload a directory to a path inside the fileshare directory."""
        subdir = self.directory_client.create_subdirectory(dest)

        source_path = Path(source).resolve()
        prefix = dest + "/"

        upload_paths = get_upload_files_from_folder(
            path=source_path,
            prefix=prefix,
            ignore_file=ignore_file,
        )

        upload_paths = sorted(upload_paths)
        self.total_file_count = len(upload_paths)

        # travers all directories recursively and create them in the fileshare
        def travers_recursively(child_dir, source_dir):
            for item in os.listdir(source_dir):
                item_path = os.path.join(source_dir, item)
                if os.path.isdir(item_path):
                    new_dir = child_dir.create_subdirectory(item)
                    travers_recursively(new_dir, item_path)

        travers_recursively(child_dir=subdir, source_dir=source)

        if show_progress:
            with DirectoryUploadProgressBar(dir_size=get_directory_size(source_path), msg=msg) as progress_bar:
                for src, destination in upload_paths:
                    self.upload_file(
                        src,
                        destination,
                        in_directory=True,
                        subdirectory_client=subdir,
                        show_progress=show_progress,
                        callback=progress_bar.update_to,
                    )
        else:
            for src, destination in upload_paths:
                self.upload_file(
                    src,
                    destination,
                    in_directory=True,
                    subdirectory_client=subdir,
                    show_progress=show_progress,
                )

    def _check_file_share_directory_exist(self, dest) -> bool:
        """Check if the file share directory exists."""
        return self.directory_client.get_subdirectory_client(dest).exists()

    def _check_file_share_file_exist(self, dest) -> bool:
        """Check if the file share directory exists."""
        if dest.startswith(self.file_share_prefix):
            dest = dest.replace(f"{self.file_share_prefix}/", "")
        file_client = self.directory_client.get_file_client(dest)
        try:
            file_client.get_file_properties()
        except Exception:
            return False
        return True

    def _delete_file_share_directory(self, dir_client) -> None:
        """Recursively delete a directory with content in the file share."""
        for item in dir_client.list_directories_and_files():
            if isinstance(item, DirectoryProperties):
                self._delete_file_share_directory(dir_client.get_subdirectory_client(item.name))
            else:
                dir_client.delete_file(item.name)

        dir_client.delete_directory()
