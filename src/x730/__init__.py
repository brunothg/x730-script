from .cli import CLI, main as _cli_main
from .daemon import Server, Client
from .x730 import X730


def main() -> None:
    """
    Run CLI entry point
    """
    _cli_main()


if __name__ == "__main__":
    main()
