from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeEndpointError(ValueError):
    pass


def _validate_endpoint(url: str, allow_private_network: bool, allowed_schemes: set[str]) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in allowed_schemes or not parsed.hostname:
        expected = " or ".join(f"{scheme}://" for scheme in sorted(allowed_schemes))
        raise UnsafeEndpointError(f"Endpoint must be an absolute {expected} URL")
    if parsed.username or parsed.password:
        raise UnsafeEndpointError("Credentials must not be embedded in the endpoint URL")
    if parsed.hostname.lower() in {"metadata.google.internal"}:
        raise UnsafeEndpointError("Cloud metadata endpoints are blocked")

    try:
        default_port = 443 if parsed.scheme in {"https", "wss"} else 80
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, parsed.port or default_port)}
    except socket.gaierror as exc:
        raise UnsafeEndpointError(f"Endpoint hostname could not be resolved: {parsed.hostname}") from exc

    for raw in addresses:
        ip = ipaddress.ip_address(raw)
        if ip == ipaddress.ip_address("169.254.169.254"):
            raise UnsafeEndpointError("Cloud metadata endpoints are blocked")
        if not allow_private_network and (
            ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
        ):
            raise UnsafeEndpointError(
                "Private or local endpoints require allow_private_network=true"
            )
    return url


def validate_endpoint(url: str, allow_private_network: bool = False) -> str:
    return _validate_endpoint(url, allow_private_network, {"http", "https"})


def validate_websocket_endpoint(url: str, allow_private_network: bool = False) -> str:
    return _validate_endpoint(url, allow_private_network, {"ws", "wss"})
