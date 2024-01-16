import socket


def find_available_port() -> int:
    """Find an available port on localhost"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        _, port = s.getsockname()
        return port
