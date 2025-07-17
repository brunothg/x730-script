import argparse
import inspect
import logging
import sys
from pathlib import Path
from typing import Callable

from .daemon import Server as DaemonServer, Client as DaemonClient, DEFAULT_PID_FILE as DAEMON_DEFAULT_PID_FILE


class CLI:
    """
    Command line interface for the x730 utility
    """
    _LOG = logging.getLogger(__name__)

    def __init__(self):
        self._parser = argparse.ArgumentParser(
            description="X730 Command line interface",
            epilog="Command line interface for controlling the [Geekworm X730 expansion board](https://wiki.geekworm.com/X730) for the Raspberry Pi."
        )
        self._parser.add_argument('-v', '--verbose', action='count', default=0, help="Increase verbosity")
        self._parser.add_argument('-p', '--pid-file', type=Path, default=DAEMON_DEFAULT_PID_FILE, dest='pid_file', help=f"PID file to use")
        subparsers = self._parser.add_subparsers(title="command", dest='command_name', required=False)

        shutdown_parser = subparsers.add_parser('shutdown', help="Shutdown the system")
        shutdown_parser.set_defaults(command=self.shutdown)
        shutdown_type_group = shutdown_parser.add_mutually_exclusive_group(required=True)
        shutdown_type_group.add_argument('-p', '--poweroff', action='store_false', dest='reboot', help="Power off the system")
        shutdown_type_group.add_argument('-r', '--reboot', action='store_true', dest='reboot', help="Reboot the system")

        daemon_parser = subparsers.add_parser('daemon', help="Start the X730 expansion board daemon")
        daemon_parser.set_defaults(command=self.daemon)

    def help(self) -> None:
        """
        Print the help message
        :return:
        """
        self._parser.print_help()

    def shutdown(self, reboot: bool = False, pid_file: Path = Path(DAEMON_DEFAULT_PID_FILE)) -> None:
        """
        Instruct the X730 expansion board to shut down
        :param reboot: If true, reboot the system, else shutdown the system
        :param pid_file: PID file to use
        :return:
        """
        with DaemonClient(pid_file=pid_file) as client:
            if reboot:
               client.reboot()
            else:
                client.poweroff()

    def daemon(self, pid_file: Path = Path(DAEMON_DEFAULT_PID_FILE)) -> None:
        """
        Start the X730 expansion board daemon
        :param pid_file: PID file to use
        :return:
        """
        with DaemonServer(pid_file=pid_file) as server:
            server.serve_until()

    def verbose(self, level: int) -> None:
        """
        Set the verbosity level
        :param level: An integer between 0 (Critical) and 4 (Debug)
        :return:
        """
        logging.basicConfig(
            level=[
                logging.CRITICAL,
                logging.ERROR,
                logging.WARNING,
                logging.INFO,
                logging.DEBUG,
            ][max(0, min(level, 4))]
        )
        CLI._LOG.debug(f"Verbose level: {level}")

    def run(self, args: list[str]) -> None:
        """
        Run the CLI with given arguments
        :param args: The command line arguments
        :return:
        """
        parsed_args = self._parser.parse_args(args)
        self.verbose(parsed_args.verbose)
        CLI._LOG.debug(f"parsed_args = {parsed_args}")

        command: Callable = getattr(parsed_args, 'command', self.help)
        command_params = [] if command is None else inspect.signature(command).parameters.keys()
        command_args = {k: v for k, v in vars(parsed_args).items() if k in command_params}

        CLI._LOG.info(f"run command: {command.__name__}({command_args})")
        command(**command_args)


def main() -> None:
    """
    Run CLI with sys.argv command line arguments.
    :return:
    """
    CLI().run(sys.argv[1:])


if __name__ == "__main__":
    main()
