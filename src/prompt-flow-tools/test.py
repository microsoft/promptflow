def test():
    # `collect_package_tools` gathers all tools info using the `package-tools` entry point. This ensures that your package is correctly packed and your tools are accurately collected. 
    from promptflow.core.tools_manager import collect_package_tools
    tools = collect_package_tools()
    print(tools)
if __name__ == "__main__":
    test()