#!/usr/bin/env python3
import dataclasses
import sys
from typing import Callable, Any
import subprocess
from pathlib import Path

SELF = Path(__file__)
SELF_DIR = SELF.parent


############
# Makefile #
############
@dataclasses.dataclass
class Target:
    name: str
    default: bool = False
    func: Callable = None
    call_limit: int = 1
    call_limit_raise: bool = False

    _call_counter: int = dataclasses.field(default=0, init=False)
    _last_result: Any = dataclasses.field(default=None, init=False)

    def make(self, *args, **kwargs) -> Any:
        return self.func(*args, **kwargs)

    def __call__(self, func: Callable = None) -> Callable:
        if self.default and get_target() is not None:
            raise RuntimeError("More than one default target is not allowed")

        def wrapper(*args, **kwargs) -> Any:
            if self._call_counter >= self.call_limit:
                if self.call_limit_raise:
                    raise RuntimeError(f"Call limit reached. Can not run '{self.name}' target.")
                else:
                    return self._last_result
            self._last_result = func(*args, **kwargs)
            self._call_counter += 1
            return self._last_result

        self.name = func.__name__ if self.name is None else self.name
        self.func = wrapper
        targets[self.name] = self
        return wrapper


targets: dict[str, Target] = {}


def get_target(name: str = None) -> Target | None:
    target: Target | None = None
    if name is None:
        target = next((x for x in targets.values() if x.default), None)
    else:
        target = targets.get(name, None)
    return target


def make(name: str = None, *args, **kwargs) -> Any:
    target = get_target(name)
    if target is None:
        print(f"Target for '{name or 'default'}' not found.")
    else:
        print(f"Run target '{name or target.name + ' (default)'}'")
        target.make(*args, **kwargs)


###########
# Targets #
###########
@Target(name="test")
def target_test():
    print("Run tests.")
    subprocess.run(
        args=[
            'uv', 'run',
            '--module', 'unittest',
            'discover',
            '--start-directory', 'tests',
            '--pattern', 'test_*.py',
            '-v'
        ],
        cwd=SELF_DIR,
        check=True
    )


@Target(name="all", default=True)
def _all():
    target_test()
    print("All done.")


########
# MAIN #
########
def main():
    for target_name in (sys.argv[1:] if len(sys.argv) > 1 else [None]):
        make(target_name)


if __name__ == '__main__':
    main()
