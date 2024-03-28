import sys
import multiprocessing

# use this file as the only entry point for the CLI to avoid packaging the same environment repeatedly

if __name__ == "__main__":
    multiprocessing.freeze_support()
    command = sys.argv[1] if len(sys.argv) > 1 else None
    sys.argv = sys.argv[1:]
    if command == 'pf':
        from promptflow._cli._pf.entry import main as pf_main
        pf_main()
    elif command == 'pfazure':
        from promptflow.azure._cli.entry import main as pfazure_main
        pfazure_main()
    else:
        print(f"Invalid command {sys.argv}. Please use 'pf', 'pfazure'.")
