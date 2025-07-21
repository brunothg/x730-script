import functools
import inspect
import logging
import os
import signal
import sys
import tempfile
import threading
import fcntl
import time
from abc import ABC
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Optional, Any, Callable, Self

from .x730 import X730

_LOG = logging.getLogger(__name__)
DEFAULT_PID_FILE: Path = Path((
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
                              )[0]) / f"{(Path(sys.argv[0]).name if len(sys.argv) > 0 else None) or X730.__name__}.pid"


class Signal:
    """
    Decorator for signals.
    """

    _decorator_attr = f"_{__name__}_signal"

    @classmethod
    def get_signals(cls, clazz: type) -> list[Self]:
        """
        Get all signals defined in a class
        :param clazz: The class to get signals for
        :return: The list of signals
        """
        return [
            sig for sig in (
                Signal.get_signal(func) for name, func
                in inspect.getmembers(clazz, inspect.isfunction)
            ) if sig is not None
        ]

    @classmethod
    def get_signal(cls, func: Callable) -> Optional[Self]:
        """
        Get a signal from a function
        :param func: The function to get a signal from
        :return: The signal or None
        """
        return getattr(func, cls._decorator_attr, None)

    @classmethod
    def set_signal(cls, func: Callable, value: Self):
        """
        Set a signal for a function
        :param func: The function to set a signal for
        :param value: The signal to set
        :return:
        """
        setattr(func, Signal._decorator_attr, value)

    def __init__(self, signum: int | Iterable[int]):
        self.signums: tuple[int] = tuple(signum if isinstance(signum, Iterable) else [signum])

    def __call__(self, func: Callable) -> Callable:
        self.func = func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            raise NotImplementedError(f"You must implement this method: {func}({args}, {kwargs})")

        Signal.set_signal(wrapper, self)
        return wrapper


class Daemon(ABC):
    """
    Daemon base class interface.
    """
    _LOG = logging.getLogger(__name__)

    def __init__(
            self,
            pid_file: Optional[Path] = None,
    ):
        self._x730 = X730()
        self._pid_file = pid_file or DEFAULT_PID_FILE

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any):
        self.close()

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

    @Signal(signum=signal.SIGUSR1)
    def reboot(self) -> None:
        """
        See: `X730.reboot`
        """
        self._x730.reboot()

    @Signal(signum=signal.SIGUSR2)
    def poweroff(self) -> None:
        """
        See: `X730.poweroff`
        """
        self._x730.poweroff()


class Server(Daemon):
    """
    Daemon Server class.
    """
    _LOG = logging.getLogger(__name__)

    def _handle_signal(self, signum: int, sigs: list[Signal]) -> None:
        """
        Handle incoming signals.
        Invokes the decorated function associated with the given signal.
        :param sigs: The signals to handle
        """
        Server._LOG.debug(f"Handle signal {signum} for {sigs}")
        for sig in sigs:
            Server._LOG.debug(f"Invoke {sig.func} for {signum}@{sig}")
            sig.func(self)

    def _register_signal_handlers(self) -> None:
        """
        Register signal handlers for decorated functions.
        """
        sig_dict: dict[int, list[Signal]] = defaultdict(list)
        [sig_dict[signum].append(sig) for sig in Signal.get_signals(self.__class__) for signum in sig.signums]
        for signum, sigs in sig_dict.items():
            signal.signal(signum, lambda _sig_nr, _frame: self._handle_signal(_sig_nr, sigs))

    def _unregister_signal_handlers(self) -> None:
        """
        Unregister signal handlers for decorated functions.
        """
        for signum in (
                signum for signums in
                (sig.signums for sig in Signal.get_signals(self.__class__))
                for signum in signums
        ):
            signal.signal(signum, signal.SIG_DFL)

    def _create_pid_file(self) -> None:
        path = self._pid_file
        Server._LOG.debug(f"Create pid file {path}")

        path.parent.mkdir(parents=True, exist_ok=True)
        pid_fd = open(path, "w")
        try:
            Server._LOG.debug(f"Lock pid file {path}")
            fcntl.flock(pid_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            pid_fd.write(str(os.getpid()))
        except (OSError, IOError) as e:
            pid_fd.close()
            Server._LOG.debug(f"Locking pid file {path} failed: {e}")
            raise e
        self._pid_fd = pid_fd

    def _rm_pid_file(self) -> None:
        path = self._pid_file
        pid_fd = self._pid_fd
        try:
            if pid_fd is not None:
                Server._LOG.debug(f"Release lock for pid file {path}")
                fcntl.flock(pid_fd, fcntl.LOCK_UN)
        finally:
            if pid_fd is not None:
                pid_fd.close()
            path.unlink()

    def serve_until(self, stop_event: Optional[threading.Event] = None):
        """
        Serve until stop_event is set or forever, if not stop_event is provided.
        :param stop_event: Event to stop serving
        """
        if stop_event is not None:
            stop_event.clear()

        while not stop_event or not stop_event.is_set():
            time.sleep(60)

    def open(self) -> None:
        super().open()

        self._create_pid_file()
        self._register_signal_handlers()

    def close(self) -> None:
        try:
            self._unregister_signal_handlers()
            self._rm_pid_file()
        finally:
            super().close()


class Client(Daemon):
    """
    Daemon Client class.
    """
    _LOG = logging.getLogger(__name__)

    @classmethod
    def static_init(cls):
        cls._patch_signals()

    @classmethod
    def _patch_signals(cls):
        """
        Patch all signal functions.
        """
        for sig in Signal.get_signals(cls):
            setattr(cls, sig.func.__name__, cls._make_patch(sig))

    @classmethod
    def _make_patch(cls, sig: Signal) -> Callable:
        """
        Make a signal patch function.
        Instead of invoking the patched function a signal will be sent to the daemon.
        :param sig: The signal to patch for.
        """

        @functools.wraps(sig.func)
        def wrapper(self: Self):
            cls._LOG.info(f"Sending signal(s) {sig.signums} for {sig.func.__name__}")
            for signum in sig.signums:
                self._signal_pid_file(signum)

        return wrapper

    def _read_pid_file(self) -> int:
        """
        Read the pid file.
        :return: The pid number
        """
        with open(self._pid_file, "r+") as pid_fd:
            try:
                Client._LOG.debug("Test pid file is locked by daemon.")
                fcntl.flock(pid_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(pid_fd, fcntl.LOCK_UN)
            except OSError as e:
                Client._LOG.debug(f"Pid file is locked by daemon: {e}")
                return int(pid_fd.read())
            Client._LOG.debug("Failed to read pid file. Not locked by daemon. Assuming not running.")
            raise RuntimeError("Failed to read pid file. Daemon not running.")

    def _signal_pid_file(self, signum: int) -> None:
        """
        Send a signal to the daemon identified by pid file.
        """
        pid = self._read_pid_file()
        Client._LOG.debug(f"send signal {signum} to pid {pid}")
        os.kill(pid, signum)


Client.static_init()
