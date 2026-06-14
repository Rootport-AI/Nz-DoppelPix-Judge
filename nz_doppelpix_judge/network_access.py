from __future__ import annotations

import socket
from functools import lru_cache
from ipaddress import ip_address
from threading import Lock
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response


LOCAL_NETWORK_DISABLED_MESSAGE = "Local network access is disabled."
LOCAL_NETWORK_DEFAULT_ENABLED = False
_LOCAL_HOSTNAMES = {"localhost", "testclient"}


class NetworkAccessControl:
    def __init__(self, local_network_enabled: bool = LOCAL_NETWORK_DEFAULT_ENABLED) -> None:
        self._local_network_enabled = local_network_enabled
        self._lock = Lock()

    def is_local_network_enabled(self) -> bool:
        with self._lock:
            return self._local_network_enabled

    def set_local_network_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._local_network_enabled = bool(enabled)


NETWORK_ACCESS = NetworkAccessControl()


def _normalize_host(host: str) -> str:
    cleaned = host.strip().strip("[]").lower()
    try:
        address = ip_address(cleaned)
    except ValueError:
        return cleaned

    if getattr(address, "ipv4_mapped", None) is not None:
        address = address.ipv4_mapped
    return str(address)


@lru_cache(maxsize=1)
def local_machine_addresses() -> frozenset[str]:
    addresses = {"127.0.0.1", "::1"}
    hostnames = {socket.gethostname(), socket.getfqdn()}
    for hostname in hostnames:
        if not hostname:
            continue
        try:
            infos = socket.getaddrinfo(hostname, None)
        except OSError:
            continue
        for info in infos:
            addresses.add(info[4][0])
    return frozenset(_normalize_host(address) for address in addresses)


def is_local_machine_client(
    host: str | None,
    local_addresses: Iterable[str] | None = None,
) -> bool:
    if not host:
        return True

    normalized = _normalize_host(host)
    if normalized in _LOCAL_HOSTNAMES:
        return True

    try:
        address = ip_address(normalized)
    except ValueError:
        return False

    if address.is_loopback:
        return True

    addresses = (
        local_machine_addresses()
        if local_addresses is None
        else frozenset(_normalize_host(item) for item in local_addresses)
    )
    return normalized in addresses


def client_is_allowed(
    host: str | None,
    local_network_enabled: bool,
    local_addresses: Iterable[str] | None = None,
) -> bool:
    return bool(local_network_enabled) or is_local_machine_client(host, local_addresses)


class LocalNetworkAccessMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, access_control: NetworkAccessControl = NETWORK_ACCESS) -> None:
        super().__init__(app)
        self._access_control = access_control

    async def dispatch(self, request: Request, call_next) -> Response:
        host = request.client.host if request.client else None
        if client_is_allowed(host, self._access_control.is_local_network_enabled()):
            return await call_next(request)
        return PlainTextResponse(LOCAL_NETWORK_DISABLED_MESSAGE, status_code=403)
