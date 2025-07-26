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
import fcntl
from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any, Callable, Self

from .x730 import X730

DEFAULT_NAME: str = (Path(sys.argv[0]).name if len(sys.argv) > 0 else None) or X730.__name__
DEFAULT_SOCK_FILE: Path = Path((
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
                               )[0]) \
                          / "DEFAULT_NAME" \
                          / f"{DEFAULT_NAME}.sock"

DEFAULT_SOCKET_TIMEOUT: float = 5
DEFAULT_RX_LIMIT: int = 10 * 1024 * 1024


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
            sock_file: Path = DEFAULT_SOCK_FILE,
            buffer_size: int = DEFAULT_RX_LIMIT,
    ):
        self._sock_file = sock_file
        self._lock_file = sock_file.with_suffix(".lock")
        self._buffer_size = buffer_size

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
        See Also:
            X730.reboot
        """
        self._reboot()

    @API(api_id=API.DEFAULT_API_ID)
    def poweroff(self, force: bool = False) -> None:
        """
        See Also:
            X730.poweroff
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
            sock_file: Path = DEFAULT_SOCK_FILE,
            buffer_size: int = DEFAULT_RX_LIMIT,
            backlog_size: Optional[int] = None,
            accept_timeout: Optional[float] = DEFAULT_SOCKET_TIMEOUT,
            client_timeout: Optional[float] = DEFAULT_SOCKET_TIMEOUT,
    ):
        super().__init__(sock_file=sock_file, buffer_size=buffer_size)
        self._backlog_size = backlog_size
        self._socket: Optional[socket.socket] = None
        self._accept_timeout = accept_timeout
        self._client_timeout = client_timeout
        self._x730 = X730()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any):
        self.close()

    def _reboot(self) -> None:
        self._x730.reboot()

    def _poweroff(self, force: bool = False) -> None:
        self._x730.poweroff(force = force)

    def _setup_socket(self):
        lock_file = self._lock_file
        Server._LOG.debug(f"Create lock {lock_file}")
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = open(lock_file, "w")
        try:
            Server._LOG.debug(f"Lock file {lock_file}")
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            lock_fd.close()
            Server._LOG.debug(f"Locking {lock_file} failed: {e}")
            raise e
        self._lock_fd = lock_fd

        sock_file = self._sock_file
        sock_file.parent.mkdir(parents=True, exist_ok=True)
        if sock_file.exists():
            sock_file.unlink()
        if not self._socket:
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.bind(str(self._sock_file))
            self._socket.listen(self._backlog_size) if self._backlog_size else self._socket.listen()
            self._socket.settimeout(self._accept_timeout)

    def _teardown_socket(self):
        _socket = self._socket
        sock_file = self._sock_file
        lock_file = self._lock_file
        lock_fd = self._lock_fd

        try:
            if _socket is not None:
                _socket.close()
                sock_file.unlink()

            if lock_fd is not None:
                Server._LOG.debug(f"Release lock file {lock_file}")
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            if lock_fd is not None:
                lock_fd.close()
            lock_file.unlink()

    def serve(self):
        # TODO serve
        pass

    def serve_until(self, stop_event: Optional[threading.Event] = None) -> None:
        """
       Serve until stop_event is set or forever, if no stop_event is provided.

       Args:
           stop_event: Event to stop serving

       Returns:
           None
       """
        if stop_event is not None:
            stop_event.clear()

        while not stop_event or not stop_event.is_set():
            try:
                self.serve()
            except Exception as e:
                Server._LOG.warning(f"Exception while serving: {e}")

    def open(self) -> None:
        super().open()

        self._x730.open()
        self._setup_socket()

    def close(self) -> None:
        try:
            self._teardown_socket()
            self._x730.close()
        finally:
            self._socket = None
            super().close()


class Client(Daemon):
    """
    Daemon Client class.
    """
    _LOG = logging.getLogger(__name__)

    @classmethod
    def static_init(cls):
        cls._patch_apis()

    @classmethod
    def _patch_apis(cls) -> None:
        """
        Patch all API functions.

        Returns:
            None
        """
        for api in API.get_apis(cls):
            setattr(cls, api.func.__name__, cls._make_patch(api))

    @classmethod
    def _make_patch(cls, api: API):
        """
        Make an API patch function.
        Instead of invoking the patched function an API call will be sent to the daemon.

        Args:
            api: The API to patch for.

        Returns:
            The patched function.
        """

        @functools.wraps(api.func)
        def wrapper(self: Self, *args: Any, **kwargs: dict[str, Any]) -> Any:
            api_request = ApiRequest(api_id=api.api_id, args=args, kwargs=kwargs)
            api_response = self._api_call(api_request)
            if api_response.exception:
                raise IOError(api_response.response)
            return api_response.response

        return wrapper

    def _api_call(self, request: ApiRequest) -> ApiResponse:
        Client._LOG.debug(f"Client API call: {request}")
        with open(self._lock_file, "r+") as lock_fd:
            try:
                Client._LOG.debug("Test lock file is locked by daemon.")
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                Client._LOG.debug("Failed to connect to sock. Not locked by daemon. Assuming not running.")
                raise RuntimeError("Failed to connect to sock. Daemon not running.")
            except OSError as e:
                Client._LOG.debug(f"Pid file is locked by daemon: {e}")

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(self._sock_file))
            client.sendall(request.to_json().encode())
            response = ApiResponse.from_json(_sock_receive_all(client, self._buffer_size).decode())
            return response


Client.static_init()
