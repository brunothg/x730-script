from .cli import CLI, main as _cli_main
from .x730 import X730

def main() -> None:
    _cli_main()

if __name__ == "__main__":
    main()
