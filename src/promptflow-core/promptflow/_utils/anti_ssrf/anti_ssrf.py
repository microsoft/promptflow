# Export the main classes for easy import
from typing import List, Optional

from .anti_ssrf_policy import AntiSSRFPolicy
from .exceptions import AntiSSRFException


# Simple wrapper class that provides validate_url method
class AntiSSRF:
    """Anti-SSRF protection class that validates URLs and network connections."""

    def __init__(self, policy: Optional[AntiSSRFPolicy] = None):
        """Initialize AntiSSRF with an optional custom policy."""
        self.policy: AntiSSRFPolicy = policy if policy is not None else AntiSSRFPolicy(use_defaults=True)

    def validate_url(self, url: str, headers={}) -> None:
        """
        Validate a URL against the Anti-SSRF policy.

        Args:
            url: The URL to validate

        Raises:
            AntiSSRFException: If the URL is not allowed by the policy
        """
        if not url:
            return

        from urllib.parse import urlparse

        # Parse the URL
        try:
            parsed_url = urlparse(url)
        except Exception as e:
            raise AntiSSRFException(f"Invalid URL format: {e}")

        if not parsed_url.hostname:
            raise AntiSSRFException("URL must have a hostname")

        # Resolve DNS and check network connections
        if parsed_url.hostname != "registries" and parsed_url.hostname != "location.api.azureml.ms":
            dns_resolved_ips = self._resolve_hostname(parsed_url.hostname)

            if not self.policy.is_network_connection_allowed(dns_resolved_ips):
                raise AntiSSRFException(f"Network connection to '{parsed_url.hostname}' is not allowed")

        # Check HTTP scheme
        if not self.policy.is_http_request_allowed(parsed_url.scheme, headers):
            raise AntiSSRFException(f"HTTP scheme '{parsed_url.scheme}' is not allowed")

    def _resolve_hostname(self, hostname: str) -> List[str]:
        """Resolve hostname to IP addresses."""
        import ipaddress
        import socket

        # Handle localhost explicitly
        if hostname.lower() == "localhost":
            return ["127.0.0.1"]

        # Try to parse as IP address first
        try:
            ip_address = ipaddress.ip_address(hostname)
            return [str(ip_address)]
        except ValueError:
            pass  # Not an IP address, continue with DNS resolution

        # Perform DNS resolution
        try:
            _, _, ip_addresses = socket.gethostbyname_ex(hostname)
            if not ip_addresses:
                raise AntiSSRFException(f"No IP addresses resolved for hostname: {hostname}")
            return ip_addresses
        except socket.gaierror as e:
            raise AntiSSRFException(f"DNS resolution failed for hostname '{hostname}': {e}")
        except Exception as e:
            raise AntiSSRFException(f"Error resolving hostname '{hostname}': {e}")
