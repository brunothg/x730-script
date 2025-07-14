import functools
import inspect
import logging
import os
import signal
import sys
import tempfile
import threading
import time
from abc import ABC
from collections import defaultdict
from pathlib import Path
from typing import Optional, Any, Callable, Self

from .x730 import X730

_LOG = logging.getLogger(__name__)
DEFAULT_PID_FILE: Path = (
                                 [
                                     p for p in
                                     (Path(p) for p in [
                                         "/run",
                                         "/var/run",
                                     ])
                                     if p.exists() and p.is_dir() and os.access(p, os.W_OK | os.X_OK)
                                 ]
                                 or [Path(tempfile.gettempdir())]
                         )[0] / f"{sys.argv[0]}.pid"

# TODO improve pid file handling
def _create_pid_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as pid_file:
        pid_file.write(str(os.getpid()))


def _rm_pid_file(path: Path) -> None:
    if path.exists():
        path.unlink()


def _read_pid_file(path: Path) -> int:
    with open(path, "r") as pid_file:
        return int(pid_file.read())


def _signal_pid_file(path: Path, signum: int) -> None:
    pid = _read_pid_file(path)
    _LOG.debug(f"send signal {signum} to pid {pid}")
    os.kill(pid, signum)


def static_init(cls: type):
    """
    Class decorator that introduces a static class init function '@classmethod __static_init__'
    :param cls: The class to decorate
    :return: The decorated (original) class
    """
    if hasattr(cls, "__static_init__"):
        cls.__static_init__()
    return cls


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

    def __init__(self, signum: int | list[int] | tuple[int]):
        self.signums: tuple[int] = tuple([signum] if type(signum) is int else signum)

    def __call__(self, func: Callable) -> Callable:
        self.func = func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            raise NotImplementedError("You must implement this method")

        Signal.set_signal(func, self)
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
        Server._LOG.debug(f"Handle signal {signum} for {sigs}")
        for sig in sigs:
            Server._LOG.debug(f"Invoke {sig.func} for {signum}@{sig}")
            sig.func()

    def _register_signal_handlers(self) -> None:
        sig_dict: dict[int, list[Signal]] = defaultdict(list)
        [sig_dict[signum].append(sig) for sig in Signal.get_signals(self.__class__) for signum in sig.signums]
        for signum, sigs in sig_dict.items():
            signal.signal(signum, lambda _sig_nr, _frame: self._handle_signal(_sig_nr, sigs))

    def _unregister_signal_handlers(self) -> None:
        for signum in (
                signum for signums in
                (sig.signums for sig in Signal.get_signals(self.__class__))
                for signum in signums
        ):
            signal.signal(signum, signal.SIG_DFL)

    def serve_until(self, stop_event: Optional[threading.Event] = None):
        if stop_event is not None:
            stop_event.clear()

        while not stop_event or not stop_event.is_set():
            time.sleep(60)

    def open(self) -> None:
        super().open()

        _create_pid_file(self._pid_file)
        self._register_signal_handlers()

    def close(self) -> None:
        try:
            self._unregister_signal_handlers()
            _rm_pid_file(self._pid_file)
        finally:
            super().close()


@static_init
class Client(Daemon):
    """
    Daemon Client class.
    """
    _LOG = logging.getLogger(__name__)

    @classmethod
    def __static_init__(cls):
        cls._patch_signals()

    @classmethod
    def _patch_signals(cls):
        for sig in Signal.get_signals(cls):
            setattr(cls, sig.func.__name__, cls._make_patch(sig))

    @classmethod
    def _make_patch(cls, sig: Signal) -> Callable:
        @functools.wraps(sig.func)
        def wrapper(self: Self):
            cls._LOG.info(f"Sending signal(s) {sig.signums} for {sig.func.__name__}")
            for signum in sig.signums:
                _signal_pid_file(self._pid_file, signum)

        return wrapper
