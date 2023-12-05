import sys

from promptflow._cli._pf.entry import main as pf_main
from promptflow._cli._pf_azure.entry import main as pfazure_main
from promptflow._sdk._service.entry import main as pfs_main


def command_pf():
    pf_main()


def command_pfazure():
    pfazure_main()


def command_pfs():
    pfs_main()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else None
    sys.argv = sys.argv[1:]
    if command == 'pf':
        command_pf()
    elif command == 'pfazure':
        command_pfazure()
    elif command == 'pfs':
        command_pfs()
    else:
        print("Invalid command. Please use 'pf', 'pfazure', or 'pfs'.")
