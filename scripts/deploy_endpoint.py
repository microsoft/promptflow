import argparse

from utils.repo_utils import create_remote_branch_in_ADO_with_new_tool_pkg_version, deploy_test_endpoint

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool_pkg_version", type=str, required=True)
    parser.add_argument("--ado_pat", type=str, required=True)
    args = parser.parse_args()
    print(f"Package version: {args.tool_pkg_version}")
    branch_name = create_remote_branch_in_ADO_with_new_tool_pkg_version(args.ado_pat, args.tool_pkg_version)
    deploy_test_endpoint(branch_name, ado_pat=args.ado_pat)
