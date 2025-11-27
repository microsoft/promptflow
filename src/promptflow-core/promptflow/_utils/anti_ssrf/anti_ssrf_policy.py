import ipaddress
from typing import List, Optional

from .cidr_helpers import IPNetwork, try_parse_cidr_string
from .exceptions import AntiSSRFException


class AntiSSRFPolicy:
    def __init__(self, use_defaults: bool = True):
        self.AllowedAddresses: List[IPNetwork] = []
        self.DeniedAddresses: List[IPNetwork] = []
        self.DeniedHeaders: List[str] = []
        self.RequiredHeaders: List[str] = []
        self.AllowPlainTextHttp: bool = False
        self.AddXFFHeader: bool = True
        self.DenyAllUnspecifiedIPs: bool = False

        if use_defaults:
            self._set_defaults()

    def add_allowed_addresses(self, networks: List[str]) -> bool:
        for network in networks:
            outnet = try_parse_cidr_string(network)
            self.AllowedAddresses.append(outnet)
        return True

    def add_denied_addresses(self, networks: List[str]) -> bool:
        if self.DenyAllUnspecifiedIPs:
            raise AntiSSRFException("Can't add denied networks when * is already supplied")
        if not networks:
            raise AntiSSRFException("Bad networks parameter")
        if len(networks) == 1 and networks[0] == "*":
            if len(self.DeniedAddresses) > 0:
                raise AntiSSRFException("Can't add * when deny list already has entries")
            self.DenyAllUnspecifiedIPs = True
            return True
        else:
            for network in networks:
                outnet = try_parse_cidr_string(network)
                self.DeniedAddresses.append(outnet)
            return True

    def add_denied_headers(self, denied_headers: Optional[List[str]]) -> None:
        if denied_headers:
            self.DeniedHeaders.extend(denied_headers)

    def add_required_headers(self, required_headers: Optional[List[str]]) -> None:
        if required_headers:
            self.RequiredHeaders.extend(required_headers)

    def set_allow_plain_text_http(self, allow_plain_text_http: bool = False) -> None:
        self.AllowPlainTextHttp = allow_plain_text_http

    def add_xff(self, add_xff: bool = True) -> None:
        self.AddXFFHeader = add_xff

    # IP Addresses in Deny List can be IPv4, IPv6 or IPv4 mapped to IPv6
    # Accordingly, to check if an input address from DNS resolution is to be denied, we should:
    # 1. Check if the input IP is an IPv4 address, and then check if it is present in deny list
    #    as a pure IPv4 or an IPv4 mapped to IPv6 format
    # 2. Check if the input IP is an IPv6 address, and then check if it is present in deny list
    #    as a pure IPv6 address. This includes addresses in IPv4 mapped to IPv6 format
    # 3. Check if the input IP is an IPv4 mapped to IPv6, then check if it is present in the
    #    deny list as an IPv4 mapped IPv6 address, then convert it to IPv4 and check if it is
    #    present in the deny list as a pure IPv4 address
    #
    # For example, 169.254.169.254, if present in the deny list, should deny DNS resolved
    # addresses 169.254.169.254 and ::ffff:a9fe:a9fe
    # Likewise ::ffff:a9fe:a9fe, if present in the deny list, should deny DNS resolved
    # addresses ::ffff:a9fe:a9fe and 169.254.169.254
    #
    # Such case-by-case comparisons leads to a lot of branches in code leading to
    # sphagettification and also makes code difficult to follow and maintain
    # Furthermore, the complexity gets compounded if one adds an allow list to the mix
    #
    # To make things easier and efficient, we convert every IPv4 address to IPv6 across the
    # deny list, allow list and also the input DNS resolved addresses
    # The CIDR helper class is accordingly written
    #
    # As IPv6 is the future anyway, this also makes the code future proof
    def is_network_connection_allowed(self, dns_resolved_ip_addresses: List[str]) -> bool:
        for ip_str in dns_resolved_ip_addresses:
            ip_address = ipaddress.ip_address(ip_str)
            ipv6_address = (
                ip_address
                if isinstance(ip_address, ipaddress.IPv6Address)
                else ipaddress.IPv6Address(f"::ffff:{ip_address}")
            )

            if self.DenyAllUnspecifiedIPs:
                # If the address is not in an allow list, it's not allowed.
                if not self._networks_contain_address(self.AllowedAddresses, ipv6_address):
                    return False
            elif self.DeniedAddresses:
                # If address is in deny list and not in allow list, it's not allowed.
                if self._networks_contain_address(
                    self.DeniedAddresses, ipv6_address
                ) and not self._networks_contain_address(self.AllowedAddresses, ipv6_address):
                    return False
        # No IP addresses returned by DNS resolution were denied
        return True

    @staticmethod
    def _networks_contain_address(networks: List[IPNetwork], address: ipaddress.IPv6Address) -> bool:
        for network in networks:
            if network.contains(address):
                return True
        return False

    def is_http_request_allowed(self, scheme: str, headers: dict) -> bool:
        if scheme.lower() == "http" and not self.AllowPlainTextHttp:
            return False

        if self.AddXFFHeader:
            if "X-Forwarded-For" not in headers:
                headers["X-Forwarded-For"] = "true"

        if self.DeniedHeaders:
            for header in self.DeniedHeaders:
                if header in headers:
                    return False

        if self.RequiredHeaders:
            for header in self.RequiredHeaders:
                if header not in headers:
                    return False

        return True

    def _set_defaults(self):
        self.AllowedAddresses = []
        self.DeniedAddresses = []
        self.RequiredHeaders = []
        self.DeniedHeaders = []
        self.AllowPlainTextHttp = False
        self.DenyAllUnspecifiedIPs = False
        self.AddXFFHeader = True

        self.add_denied_addresses(
            [
                # ==== IPv4 ==== #
                "255.255.255.255/32",
                "168.63.129.16/32",  # Not nonroutable,
                # but this is the WireServer IP we should block.
                "192.0.0.0/24",
                "192.0.2.0/24",
                "192.88.99.0/24",
                "198.51.100.0/24",
                "203.0.113.0/24",
                "169.254.0.0/16",
                "192.168.0.0/16",
                "198.18.0.0/15",
                "172.16.0.0/12",
                "100.64.0.0/10",  # IANA-Reserved
                "0.0.0.0/8",
                "10.0.0.0/8",
                "127.0.0.0/8",
                "25.0.0.0/8",  # GNS Core
                "224.0.0.0/4",
                "240.0.0.0/4",
                # ==== IPv6 ==== #
                "::1/128",  # Localhost
                "FC00::/7",  # Unique-local
                "fe80::/10",  # Link-local
                "fec0::/10",  # Site-local
                "2001::/32",  # Teredo
            ]
        )
        self.DenyAllUnspecifiedIPs = False

    # Deprecated method, for backward compatibility only
    def set_defaults(self):
        self._set_defaults()
