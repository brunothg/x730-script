import dataclasses
import functools
import inspect
import json
import logging
import os
import socket
import sys
import tempfile
import threading
from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any, Callable, Self

from .x730 import X730

DEFAULT_NAME: str = f"{(Path(sys.argv[0]).name if len(sys.argv) > 0 else None) or X730.__name__}"

DEFAULT_RUN_DIR: Path = Path((
                                     [
                                         p for p in
                                         (Path(p).resolve() for p in [
                                             "/run",
                                             "/var/run",
                                             f"/run/user/{os.geteuid()}",
                                             f"/var/run/user/{os.geteuid()}",
                                         ])
                                         if (p.exists()
                                             and p.is_dir()
                                             and os.access(p, os.W_OK | os.X_OK, effective_ids=True))
                                     ]
                                     or [tempfile.gettempdir()]
                             )[0]) / f"{DEFAULT_NAME}"

DEFAULT_PID_FILE: Path = DEFAULT_RUN_DIR / f"{DEFAULT_NAME}.pid"
DEFAULT_SOCK_FILE: Path = DEFAULT_RUN_DIR / f"{DEFAULT_NAME}.sock"


class API:
    """
    Decorator for APIs.
    """

    _decorator_attr = f"_{__name__}_api"

    DEFAULT_API_ID: str = ''

    @classmethod
    def api_id(cls, func: Callable) -> str:
        """
        Generate default API ID for function

        Args:
            func: The function to generate an API ID for
        """
        return f"{func.__qualname__}"

    @classmethod
    def get_apis(cls, clazz: type) -> list[Self]:
        """
        Get all APIs defined in a class

        Args:
            clazz: The class to get APIs for

        Returns:
            The list of APIs
        """
        return [
            api for api in (
                API.get_api(func) for name, func
                in inspect.getmembers(clazz, inspect.isfunction)
            ) if api is not None
        ]

    @classmethod
    def get_api(cls, func: Callable) -> Optional[Self]:
        """
        Get an API from a function

        Args:
            func: The function to get a API from

        Returns:
            The API or None
        """
        return getattr(func, cls._decorator_attr, None)

    @classmethod
    def set_api(cls, func: Callable, value: Self) -> None:
        """
        Set an API for a function

        Args:
            func: The function to set a API for
            value: The API to set

        Returns:
            None
        """
        setattr(func, API._decorator_attr, value)

    def __init__(self, api_id: str):
        self.api_id: str = api_id

    def __call__(self, func: Callable) -> Callable:
        self.func = func
        self.api = self.api_id or API.get_api(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)

        API.set_api(wrapper, self)
        return wrapper


class Daemon(ABC):
    """
    Daemon base class interface.
    """
    _LOG = logging.getLogger(__name__)

    def __init__(
            self,
            pid_file: Path = DEFAULT_PID_FILE,
            sock_file: Path = DEFAULT_SOCK_FILE,
    ):
        self._pid_file = pid_file
        self.sock_file = sock_file

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any):
        self.close()

    def _reboot(self) -> None:
        """
        See Also:
            reboot(): The corresponding API method
        """
        raise NotImplementedError()

    def _poweroff(self, force: bool = False) -> None:
        """
        See Also:
            poweroff(): The corresponding API method
        """
        raise NotImplementedError()

    def open(self) -> None:
        """
        Open the daemon.
        :return:
        """
        pass

    def close(self) -> None:
        """
        Close the daemon.
        :return:
        """
        pass

    @API(api_id=API.DEFAULT_API_ID)
    def reboot(self) -> None:
        """
        See: `X730.reboot`
        """
        self._reboot()

    @API(api_id=API.DEFAULT_API_ID)
    def poweroff(self, force: bool = False) -> None:
        """
        See: `X730.poweroff`
        """
        self._poweroff(force=force)


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
