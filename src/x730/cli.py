import argparse
import sys
import inspect
import logging
from typing import Callable


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
        subparsers = self._parser.add_subparsers(title="command", dest='command_name', required=False)

        shutdown_parser = subparsers.add_parser('shutdown', help="Shutdown the system")
        shutdown_parser.set_defaults(command=self.shutdown)
        shutdown_type_group = shutdown_parser.add_mutually_exclusive_group(required=True)
        shutdown_type_group.add_argument('-p', '--poweroff', action='store_false', dest='restart', help="Power off the system")
        shutdown_type_group.add_argument('-r', '--restart', action='store_true', dest='restart', help="Restart the system")

        daemon_parser = subparsers.add_parser('daemon', help="Start the X730 expansion board daemon")
        daemon_parser.set_defaults(command=self.daemon)

    def help(self) -> None:
        self._parser.print_help()

    def shutdown(self, restart: bool = False) -> None:
        # TODO shutdown
        pass

    def daemon(self) -> None:
        # TODO daemon
        pass

    def verbose(self, level: int) -> None:
        logging.basicConfig(
            level=[
                logging.CRITICAL,
                logging.ERROR,
                logging.WARNING,
                logging.INFO,
                logging.DEBUG,
            ][max(0, min(level, 4))]
        )

    def run(self, args: list[str]) -> None:
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
