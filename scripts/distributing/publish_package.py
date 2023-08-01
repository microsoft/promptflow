import argparse
import json
import os
import re
from datetime import datetime, timedelta

from azure.storage.blob import (
    AccountSasPermissions,
    BlobServiceClient,
    ContentSettings,
    ResourceTypes,
    generate_account_sas,
)


def get_connection_string(storage_account, storage_key):
    return f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key};EndpointSuffix=core.windows.net"  # noqa: E501


def get_object_sas_token(storage_account, storage_key):
    sas_token = generate_account_sas(
        account_name=storage_account,
        account_key=storage_key,
        resource_types=ResourceTypes(object=True),
        permission=AccountSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(days=365),
    )
    return sas_token


def get_wheel_distribution_name(package_name):
    """The wheel filename is {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl.
    The distribution name is normalized from the package name."""
    return package_name.replace(".", "_").replace("-", "_").replace(" ", "_")


def package_name_based_blob_prefix(package_name):
    """Convert package name to a valid blob prefix."""
    prefix = package_name.replace(".", "-")
    prefix = prefix.replace("_", "-")
    prefix = prefix.lower()
    return prefix


def override_version_with_latest(distribution_name):
    pattern = r"-\d+\.\d+\.\d+(\.\w+)?(\w+)?-"
    return re.sub(pattern, "-latest-", distribution_name, count=1)


def publish_package_internal(package_dir_path, storage_key, release_config):
    index = release_config["index"]
    index_config = config_json["targets"][index]
    storage_account = index_config["storage_account"]
    packages_container = index_config["packages_container"]
    index_container = index_config["index_container"]
    blob_prefix = index_config["blob_prefix"]
    pypi_endpoint = index_config["endpoint"]

    account_url = f"https://{storage_account}.blob.core.windows.net"
    wheel_pattern = re.compile(r".+\.whl$")
    whl_distributions = [d for d in os.listdir(package_dir_path) if wheel_pattern.match(d)]
    if len(whl_distributions) != 1:
        print(
            f"[Error] Found {len(whl_distributions)} wheel distributions in {package_dir_path}. "
            "There should be exactly one."
        )
        exit(1)
    whl_distribution = whl_distributions[0]

    # Create the BlobServiceClient with connection string
    blob_service_client = BlobServiceClient.from_connection_string(get_connection_string(storage_account, storage_key))
    container_client = blob_service_client.get_container_client(packages_container)

    # Upload the wheel package to blob storage
    package_blob = os.path.join(blob_prefix, whl_distribution)
    package_blob_client = blob_service_client.get_blob_client(container=packages_container, blob=package_blob)
    upload_file_path = os.path.join(package_dir_path, whl_distribution)
    with open(file=upload_file_path, mode="rb") as package_file:
        print(f"[Debug] Uploading {whl_distribution} to container: {packages_container}, blob: {package_blob}...")
        package_blob_client.upload_blob(package_file, overwrite=True)

    if upload_as_latest:
        latest_distribution = override_version_with_latest(whl_distribution)
        latest_package_blob = os.path.join(blob_prefix, latest_distribution)
        latest_package_blob_client = blob_service_client.get_blob_client(
            container=packages_container, blob=latest_package_blob
        )
        upload_file_path = os.path.join(package_dir_path, whl_distribution)
        with open(file=upload_file_path, mode="rb") as package_file:
            print(
                f"[Debug] Uploading {whl_distribution} as latest distribution to "
                f"container: {packages_container}, blob: {latest_package_blob}..."
            )
            latest_package_blob_client.upload_blob(package_file, overwrite=True)

    # List the blobs and generate download sas urls
    sas_token = get_object_sas_token(storage_account, storage_key)
    print(f"Listing wheel packages with prefix {blob_prefix} in container...")
    blob_list = container_client.list_blobs(name_starts_with=f"{blob_prefix}/")
    distribution_blobs = [d for d in blob_list if wheel_pattern.match(d.name)]
    # Reverse the list so that the latest distribution is at the top
    distribution_blobs.reverse()
    packages_indexes = {}  # {package_name: [distributions]}
    for blob in distribution_blobs:
        distribution_name = blob.name.split("/")[-1]
        package_name = package_name_based_blob_prefix(distribution_name.split("-")[0])
        print(f"[Debug] Blob: {blob.name}. Package distribution: {distribution_name}. Package name: {package_name}")
        download_link = f"{account_url}/{blob.container}/{blob.name}?{sas_token}"
        index_item = f"<a href='{download_link}' rel='external'>{distribution_name}</a><br/>"
        if package_name in packages_indexes:
            packages_indexes[package_name].append(index_item)
        else:
            packages_indexes[package_name] = [index_item]

    # Update index.html in the top level blob prefix for the project
    project_index_file = "project_index.html"
    with open(project_index_file, "w", encoding="utf8") as index_file:
        index_file.write("<!DOCTYPE html>\n")
        index_file.write(
            "<html lang='en'><head><meta charset='utf-8'>"
            "<meta name='api-version' value='2'/>"
            "<title>Simple Index</title></head><body>\n"
        )
        for package_name in packages_indexes:
            package_index_url = f"https://{pypi_endpoint}/{blob_prefix}/{package_name}"
            print(f"[Debug] Updated package_index_url: {package_index_url}")
            index_file.write(f"<a href='{package_index_url}'>{package_name}</a><br/>\n")
        index_file.write("</body></html>\n")

    project_index_blob = os.path.join(blob_prefix, "index.html")
    project_index_blob_client = blob_service_client.get_blob_client(container=index_container, blob=project_index_blob)
    content_settings = ContentSettings(content_type="text/html")
    with open(file=project_index_file, mode="rb") as index:
        print(f"Uploading {project_index_file} to container: {index_container}, blob: {project_index_blob}...")
        project_index_blob_client.upload_blob(index, overwrite=True, content_settings=content_settings)

    # Update index.html for the package distributions
    for package_name, distribution_indexes in packages_indexes.items():
        package_index_file = f"{package_name}_index.html"
        if len(distribution_indexes) > 0:
            print(f"{len(distribution_indexes)} distributions found for package {package_name}. Updating index.html...")
            with open(package_index_file, "w", encoding="utf8") as index_file:
                index_file.write("<!DOCTYPE html>\n")
                index_file.write(
                    f"<html lang='en'><head><meta charset='utf-8'><title>{package_name}</title></head><body>\n"
                )
                for item in distribution_indexes:
                    index_file.write(f"{item}\n")
                index_file.write("</body></html>\n")

            # Update the index.html to the blob with prefix: <blob_prefix>/<normalized package_name>
            index_blob = os.path.join(blob_prefix, package_name, "index.html")
            index_blob_client = blob_service_client.get_blob_client(container=index_container, blob=index_blob)
            content_settings = ContentSettings(content_type="text/html")
            with open(file=package_index_file, mode="rb") as index:
                print(f"Uploading {package_index_file} to container: {index_container}, blob: {index_blob}...")
                index_blob_client.upload_blob(index, overwrite=True, content_settings=content_settings)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str)
    parser.add_argument("--src_folder_name", type=str)
    parser.add_argument("--package_dir_path", type=str)
    parser.add_argument("--storage_key", type=str)
    parser.add_argument("--upload_as_latest", type=str, default="False")
    parser.add_argument("--pypi_type", type=str, default="internal")  # internal or public pypi
    parser.add_argument("--release_type", type=str, default="release")  # release or test
    args = parser.parse_args()

    print("[Debug] Arguments:")
    print(f"[Debug] config: {args.config}")
    print(f"[Debug] src_folder_name: {args.src_folder_name}")
    print(f"[Debug] package_dir_path: {args.package_dir_path}")
    upload_as_latest = args.upload_as_latest.lower() == "true"
    print(f"[Debug] upload_as_latest: {args.upload_as_latest}. Boolean upload_as_latest: {upload_as_latest}")
    print(f"[Debug] pypi_type: {args.pypi_type}")
    print(f"[Debug] release_type: {args.release_type}")

    cwd = os.getcwd()
    print(f"Current working directory: {cwd}")
    with open(os.path.join(os.getcwd(), args.config), "r") as config_file:
        config_json = json.load(config_file)

    package_dir_path = os.path.join(cwd, args.package_dir_path)
    release_config = config_json["releases"][args.pypi_type][f"{args.src_folder_name}-{args.release_type}"]

    if args.pypi_type == "internal":
        publish_package_internal(package_dir_path, args.storage_key, release_config)
