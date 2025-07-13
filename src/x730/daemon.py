import dataclasses
import functools
import json
import logging
import os
import socket
import stat
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TypeAlias, Optional, Any, Callable, Self

from .x730 import X730


def _fq_name(obj: Any) -> str:
    return f"{obj.__module__}.{obj.__qualname__}"


def _sock_receive_all(sock, limit: Optional[int] = None) -> bytes:
    buffer = bytearray()
    while True:
        if not (limit is None or len(buffer) < limit):
            raise OverflowError("socket receive limit exceeded")
        data = sock.recv(4096 if limit is None else limit - len(buffer))
        if not data:  # Socket closed
            break
        buffer.extend(data)
    return bytes(buffer)


def _unix_sockets_supported() -> bool:
    """
    Test if unix sockets are supported.
    :return: True if unix sockets are supported, else False.
    """
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.close()
        return True
    except (OSError, AttributeError):
        return False


UX_ADDR: TypeAlias = str | Path | PathLike[str]
IP_ADDR: TypeAlias = tuple[str, int]
ADDR: TypeAlias = UX_ADDR | IP_ADDR


def _is_ip_address(addr: ADDR) -> bool:
    return isinstance(addr, tuple)


def _is_ux_addr(addr: ADDR) -> bool:
    return not _is_ip_address(addr)


_DEFAULT_UX_ADDR: UX_ADDR = Path("/var/run/x730/x730.sock")
_DEFAULT_IP_ADDR: IP_ADDR = ("localhost", 24730)
_DEFAULT_ADDR: ADDR = _DEFAULT_UX_ADDR if _unix_sockets_supported() else _DEFAULT_IP_ADDR


def _is_unix_socket_active(addr: UX_ADDR) -> bool:
    addr_path = Path(addr)
    if not addr_path.exists() or not stat.S_ISSOCK(os.stat(addr_path).st_mode):
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(addr)
        return True
    except Exception:
        return False


def _prepare_ux_addr(addr: UX_ADDR):
    addr_path = Path(addr)
    addr_dir = addr_path.parent
    addr_dir.mkdir(parents=True, exist_ok=True)
    if not _is_unix_socket_active(addr):
        addr_path.unlink()


def _clean_ux_addr(addr: UX_ADDR):
    addr_path = Path(addr)
    addr_path.unlink()


def _create_socket(addr: ADDR) -> socket.socket:
    _socket: socket.socket
    if _is_ux_addr(addr):
        _socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    else:
        _socket = socket.socket(
            socket.AF_INET6 if socket.has_dualstack_ipv6() else socket.AF_INET
            , socket.SOCK_STREAM
        )
    return _socket


_DEFAULT_RX_LIMIT: int = 10 * 1024 * 1024
_DEFAULT_SOCKET_TIMEOUT: float = 5


class API:
    """
    API collection
    """
    _apis: dict[str, Callable] = {}

    @classmethod
    def get(cls, api_id: str) -> Callable:
        """
        Get api method by id
        :param api_id: The api id
        :return: The api method
        """
        return cls._apis[api_id]

    @classmethod
    def api_id(cls, func: Callable) -> str:
        """
        Get api id for method
        :param func: The api method
        :return: The api id
        """
        return _fq_name(func)

    @classmethod
    def expose(cls, func: Optional[Callable] = None) -> Callable:
        """
        Decorator to register an API function.
        :param func: The function to expose as an API.
        :return: The API function.
        """
        def decorator(_func: Callable) -> Callable:
            api_id = API.api_id(func)
            cls._apis[api_id] = _func

            @functools.wraps(_func)
            def wrapper(self: 'Daemon', *args: Any, **kwargs: Any) -> Any:
                return self._api_call(api_id, *args, **kwargs)

            return wrapper

        if callable(func):
            return decorator(func)
        else:
            return decorator


class Daemon(ABC):
    """
    Daemon base class interface.
    """
    _LOG = logging.getLogger(__name__)

    def __init__(self):
        self._x730 = X730()

    @abstractmethod
    def _api_call(self, api_id: str, *args, **kwargs) -> Any:
        """
        Called when an API call is made.
        :param api_id: The API ID.
        :param args: The API args.
        :param kwargs: The API kwargs.
        :return: The API response.
        """
        raise NotImplementedError()

    def open(self) -> None:
        """
        Open the daemon.
        :return:
        """
        self._x730.open()

    def close(self) -> None:
        """
        Close the daemon.
        :return:
        """
        self._x730.close()

    @API.expose
    def reboot(self) -> None:
        """
        See: `X730.reboot`
        """
        self._x730.reboot()

    @API.expose
    def poweroff(self, force: bool = False) -> None:
        """
        See: `X730.poweroff`
        """
        self._x730.poweroff(force=force)


@dataclass
class ApiRequest:
    api_id: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self))

    @classmethod
    def from_json(cls, json_value: str) -> Self:
        return ApiRequest(**json.loads(json_value))


@dataclass
class ApiResponse:
    api_id: str
    response: Any
    exception: bool

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self))

    @classmethod
    def from_json(cls, json_value: str) -> Self:
        return ApiResponse(**json.loads(json_value))


class Server(Daemon):
    """
    Daemon Server class.
    """
    _LOG = logging.getLogger(__name__)

    def __init__(
            self,
            addr: Optional[ADDR] = None,
            buffer_size: Optional[int] = None,
            backlog_size: Optional[int] = None,
            accept_timeout: Optional[float] = _DEFAULT_SOCKET_TIMEOUT,
            client_timeout: Optional[float] = _DEFAULT_SOCKET_TIMEOUT,
    ):
        super().__init__()
        self._addr = addr or _DEFAULT_ADDR
        self._socket: Optional[socket.socket] = None
        self._buffer_size = buffer_size or _DEFAULT_RX_LIMIT
        self._backlog_size = backlog_size
        self._accept_timeout = accept_timeout
        self._client_timeout = client_timeout

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any):
        self.close()

    def _api_call(self, api_id: str, *args, **kwargs) -> Any:
        Server._LOG.debug(f"Server API call {api_id}: args: {args}, kwargs: {kwargs}")
        return API.get(api_id)(*args, **kwargs)

    def _client_handler(self, client: socket.socket) -> None:
        client.settimeout(self._client_timeout)
        api_raw_request = _sock_receive_all(client, self._buffer_size).decode()
        if not api_raw_request:
            return

        api_request = ApiRequest.from_json(api_raw_request)
        api_response: ApiResponse
        try:
            response = self._api_call(api_request.api_id, *api_request.args, **api_request.kwargs)
            api_response = ApiResponse(api_id=api_request.api_id, response=response, exception=False)
        except Exception as e:
            api_response = ApiResponse(api_id=api_request.api_id, response=str(e), exception=True)
        client.sendall(api_response.to_json().encode())

    def serve(self):
        with self._socket.accept()[0] as client:
            self._client_handler(client)

    def serve_until(self, stop_event: Optional[threading.Event] = None):
        if stop_event is not None:
            stop_event.clear()

        while not stop_event or not stop_event.is_set():
            try:
                self.serve()
            except Exception as e:
                Server._LOG.warning(f"Exception while serving: {e}")

    def open(self) -> None:
        super().open()
        if not self._socket:
            if _is_ux_addr(self._addr):
                _prepare_ux_addr(self._addr)
            self._socket = _create_socket(self._addr)
            self._socket.bind(self._addr)
            self._socket.listen(self._backlog_size) if self._backlog_size else self._socket.listen()
            self._socket.settimeout(self._accept_timeout)

    def close(self) -> None:
        try:
            if self._socket:
                self._socket.close()
                if _is_ux_addr(self._addr):
                    _clean_ux_addr(self._addr)

        finally:
            self._socket = None
            super().close()


class Client(Daemon):
    """
    Daemon Client class.
    """
    _LOG = logging.getLogger(__name__)

    def __init__(
            self,
            addr: Optional[ADDR] = None,
            buffer_size: Optional[int] = None,
            socket_timeout: Optional[float] = _DEFAULT_SOCKET_TIMEOUT,
    ):
        super().__init__()
        self._addr = addr or _DEFAULT_ADDR
        self._buffer_size = buffer_size or _DEFAULT_RX_LIMIT
        self._socket_timeout = socket_timeout

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any):
        self.close()

    def _connect(self) -> socket.socket:
        _socket = _create_socket(self._addr)
        _socket.connect(self._addr)
        _socket.settimeout(self._socket_timeout)
        return _socket

    def _api_call(self, api_id: str, *args, **kwargs) -> Any:
        Client._LOG.debug(f"Client API call {api_id}: args: {args}, kwargs: {kwargs}")
        with self._connect() as client:
            api_request = ApiRequest(api_id=api_id, args=args, kwargs=kwargs)
            client.sendall(api_request.to_json().encode())

            api_response = ApiResponse.from_json(_sock_receive_all(client, self._buffer_size).decode())
            if api_response.exception:
                raise IOError(api_response.response)
            return api_response.response
