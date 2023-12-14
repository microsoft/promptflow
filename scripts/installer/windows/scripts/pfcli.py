import sys

# use this file as the only entry point for the CLI to avoid packaging the same environment repeatedly

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else None
    sys.argv = sys.argv[1:]
    if command == 'pf':
        from promptflow._cli._pf.entry import main as pf_main
        pf_main()
    elif command == 'pfazure':
        from promptflow._cli._pf_azure.entry import main as pfazure_main
        pfazure_main()
    elif command == 'pfs':
        from promptflow._sdk._service.entry import main as pfs_main
        pfs_main()
    elif command == 'pfsvc':
        from promptflow._sdk._service.pfsvc import init as pfsvc_init
        pfsvc_init()
    else:
        print("Invalid command. Please use 'pf', 'pfazure', 'pfs' or 'pfsvc'.")
