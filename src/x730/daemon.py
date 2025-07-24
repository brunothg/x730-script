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

        Args:
            clazz: The class to get signals for

        Returns:
            The list of signals
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

        Args:
            func: The function to get a signal from

        Returns:
            The signal or None
        """
        return getattr(func, cls._decorator_attr, None)

    @classmethod
    def set_signal(cls, func: Callable, value: Self) -> None:
        """
        Set a signal for a function

        Args:
            func: The function to set a signal for
            value: The signal to set

        Returns:
            None
        """
        setattr(func, Signal._decorator_attr, value)

    def __init__(self, signum: int | Iterable[int]):
        self.signums: tuple[int] = tuple(signum if isinstance(signum, Iterable) else [signum])

    def __call__(self, func: Callable) -> Callable:
        self.func = func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)

        Signal.set_signal(wrapper, self)
        return wrapper


class Daemon(ABC):
    """
    Daemon base class interface.
    """
    _LOG = logging.getLogger(__name__)

    def __init__(
            self,
            pid_file: Path = DEFAULT_PID_FILE,
    ):
        self._pid_file = pid_file

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

    def _poweroff(self) -> None:
        """
        See Also:
            poweroff(): The corresponding API method
        """
        raise NotImplementedError()

    def open(self) -> None:
        """
        Open the daemon.

        Returns:
            None
        """
        pass

    def close(self) -> None:
        """
        Close the daemon.

        Returns:
            None
        """
        pass

    @Signal(signum=signal.SIGUSR1)
    def reboot(self) -> None:
        """
        See:
            `X730.reboot`

        Returns:
            None
        """
        self._reboot()

    @Signal(signum=signal.SIGUSR2)
    def poweroff(self) -> None:
        """
        See:
            `X730.poweroff`

        Returns:
            None
        """
        self._poweroff()


class Server(Daemon):
    """
    Daemon Server class.
    """
    _LOG = logging.getLogger(__name__)

    def __init__(
            self,
            pid_file: Optional[Path] = None,
    ):
        super().__init__(pid_file)

        self._x730: X730 = X730()

    def _handle_signal(self, signum: int, sigs: list[Signal]) -> None:
        """
        Handle incoming signals.
        Invokes the decorated function associated with the given signal.

        Args:
            sigs: The signals to handle

        Returns:
            None
        """
        Server._LOG.debug(f"Handle signal {signum} for {sigs}")
        for sig in sigs:
            Server._LOG.debug(f"Invoke {sig.func} for {signum}@{sig}")
            sig.func(self)

    def _register_signal_handlers(self) -> None:
        """
        Register signal handlers for decorated functions.

        Returns:
            None
        """
        sig_dict: dict[int, list[Signal]] = defaultdict(list)
        [sig_dict[signum].append(sig) for sig in Signal.get_signals(self.__class__) for signum in sig.signums]
        for signum, sigs in sig_dict.items():
            signal.signal(signum, lambda _sig_nr, _frame: self._handle_signal(_sig_nr, sigs))

    def _unregister_signal_handlers(self) -> None:
        """
        Unregister signal handlers for decorated functions.

        Returns:
            None
        """
        for signum in (
                signum for signums in
                (sig.signums for sig in Signal.get_signals(self.__class__))
                for signum in signums
        ):
            signal.signal(signum, signal.SIG_DFL)

    def _create_pid_file(self) -> None:
        """
        Create and lock the pid file.

        Returns:
            None

        Raises:
            IOError: If pid file can not be created or written.
            OSError: If pid file can not be locked.
        """
        path = self._pid_file
        Server._LOG.debug(f"Create pid file {path}")

        path.parent.mkdir(parents=True, exist_ok=True)
        pid_fd = open(path, "w")
        try:
            Server._LOG.debug(f"Lock pid file {path}")
            fcntl.flock(pid_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            pid_fd.write(str(os.getpid()))
            pid_fd.flush()
        except (OSError, IOError) as e:
            pid_fd.close()
            Server._LOG.debug(f"Locking pid file {path} failed: {e}")
            raise e
        self._pid_fd = pid_fd

    def _rm_pid_file(self) -> None:
        """
        Remove and unlock the pid file.

        Returns:
            None
        """
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

    def _reboot(self) -> None:
        self._x730.reboot()

    def _poweroff(self) -> None:
        self._x730.poweroff()

    def serve_until(self, stop_event: Optional[threading.Event] = None) -> None:
        """
        Serve until stop_event is set or forever, if not stop_event is provided.

        Args:
            stop_event: Event to stop serving

        Returns:
            None
        """
        if stop_event is not None:
            stop_event.clear()

        while not stop_event or not stop_event.is_set():
            time.sleep(60)

    def open(self) -> None:
        super().open()

        self._x730.open()
        self._create_pid_file()
        self._register_signal_handlers()

    def close(self) -> None:
        try:
            self._unregister_signal_handlers()
            self._rm_pid_file()
            self._x730.close()
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
    def _patch_signals(cls) -> None:
        """
        Patch all signal functions.

        Returns:
            None
        """
        for sig in Signal.get_signals(cls):
            setattr(cls, sig.func.__name__, cls._make_patch(sig))

    @classmethod
    def _make_patch(cls, sig: Signal) -> Callable:
        """
        Make a signal patch function.
        Instead of invoking the patched function a signal will be sent to the daemon.

        Args:
            sig: The signal to patch for.

        Returns:
            The patched function.
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

        Returns:
            The pid number

        Raises:
            IOError: If the pid file is not found.
            RuntimeError: If the demon process is not running (unlocked pid file).
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

        Returns:
            None
        """
        pid = self._read_pid_file()
        Client._LOG.debug(f"send signal {signum} to pid {pid}")
        os.kill(pid, signum)


Client.static_init()
