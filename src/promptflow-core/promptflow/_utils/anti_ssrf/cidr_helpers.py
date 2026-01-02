import ipaddress
from typing import Union

from .exceptions import AntiSSRFException


class IPNetwork:
    def __init__(self, ip: Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address], prefix: int) -> None:
        self._base_address = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
        self._prefix_length = prefix

    def contains(self, ip: Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
        ip_obj = ip
        if isinstance(ip, str):
            ip_obj = ipaddress.ip_address(ip)
        # Convert IPv4 to IPv6-mapped if base is IPv6
        if self._base_address.version == 6 and ip_obj.version == 4:
            ip_obj = ipaddress.IPv6Address(f"::ffff:{ip_obj}")
        return ip_obj in self._base_address


def _parse_ip_address(ip_string: str) -> Union[ipaddress.IPv4Address, ipaddress.IPv6Address]:
    """Parse IP address from string, raising AntiSSRFException on error."""
    try:
        return ipaddress.ip_address(ip_string)
    except ValueError as e:
        raise AntiSSRFException("Bad CIDR", e)


def _parse_prefix_length(prefix_string: str) -> int:
    """Parse prefix length from string, raising AntiSSRFException on error."""
    try:
        return int(prefix_string)
    except ValueError as e:
        raise AntiSSRFException("Bad CIDR", e)


def _create_single_ip_network(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> IPNetwork:
    """Create network for single IP address (no prefix specified)."""
    if ip.version == 4:
        # IPv4 mapped to IPv6, /128
        return IPNetwork(f"::ffff:{ip}", 128)
    elif ip.version == 6:
        return IPNetwork(ip, 128)
    else:
        raise AntiSSRFException("Bad CIDR")


def _create_prefixed_network(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address], prefix_length: int) -> IPNetwork:
    """Create network for IP address with prefix."""
    if ip.version == 4 and 0 <= prefix_length <= 32:
        # IPv4 mapped to IPv6, prefix + 96
        return IPNetwork(f"::ffff:{ip}", prefix_length + 96)
    elif ip.version == 6 and 0 <= prefix_length <= 128:
        return IPNetwork(ip, prefix_length)
    else:
        raise AntiSSRFException("Bad CIDR")


# Try parse CIDR string
# Returns an IPNetwork object if everything went fine, or throws an exception
# For easy computation of allow/deny, every IP Address is converted into an IPv6 address
def try_parse_cidr_string(cidr_string: str) -> IPNetwork:
    parts = cidr_string.split("/")
    ip = _parse_ip_address(parts[0])

    if len(parts) == 1:
        # e.g. "127.0.0.1" or "::ffff:909:909"
        return _create_single_ip_network(ip)
    elif len(parts) == 2:
        # Cases such as "127.0.0.1/2" or "::ffff:909:909/80"
        prefix_length = _parse_prefix_length(parts[1])
        return _create_prefixed_network(ip, prefix_length)
    else:
        raise AntiSSRFException("Bad CIDR")
