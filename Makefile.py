#!/usr/bin/env python3
import dataclasses
import os
import shutil
import subprocess
import sys
from string import Template
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

SELF = Path(__file__)
SELF_DIR = SELF.parent

SYSTEMD_DIR = Path("/etc/systemd/system")
UV_TOOL_DIR = Path("/opt/uv/tools")
UV_TOOL_BIN_DIR = Path("/usr/local/bin")


############
# Makefile #
############
@dataclass
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


@Target(name="build")
def target_build():
    print("Run build.")
    subprocess.run(
        args=[
            'uv', 'build'
        ],
        cwd=SELF_DIR,
        check=True
    )


@Target(name="install")
def target_install():
    print("Run install.")
    target_build()

    subprocess.run(
        args=[
            'uv', 'tool', 'install', '.'
        ],
        cwd=SELF_DIR,
        env={
                'UV_TOOL_DIR': str(UV_TOOL_DIR),
                'UV_TOOL_BIN_DIR': str(UV_TOOL_BIN_DIR),
            } | dict(os.environ),
        check=True
    )
    x730 = shutil.which('x730')
    if x730 is None:
        raise RuntimeError(' '.join([
            "x730 could not be found."
            "You may need to install it to another path or update your PATH environment variable."
        ]))

    for unit_file in (SELF_DIR / "src" / "systemd").glob("*.service"):
        with open(unit_file, 'r', encoding='utf-8') as fd_unit_file:
            template_unit_file = Template(fd_unit_file.read())
        dst = SYSTEMD_DIR / unit_file.name
        with open(dst, 'w') as fd_dst:
            fd_dst.write(template_unit_file.substitute({
                'x730': x730,
            }))
        os.chmod(dst, 0o644)

    for unit_file in SYSTEMD_DIR.glob("x730*.service"):
        subprocess.run(args=['systemctl', 'enable', unit_file.name])


@Target(name="uninstall")
def target_uninstall():
    print("Run uninstall.")

    for unit_file in SYSTEMD_DIR.glob("x730*.service"):
        subprocess.run(args=['systemctl', 'disable', '--now', unit_file.name])

    for unit_file in SYSTEMD_DIR.glob("x730*.service"):
        unit_file.unlink()

    subprocess.run(
        args=[
            'uv', 'tool', 'uninstall', 'x730'
        ],
        cwd=SELF_DIR,
        env={
                'UV_TOOL_DIR': str(UV_TOOL_DIR),
                'UV_TOOL_BIN_DIR': str(UV_TOOL_BIN_DIR),
            } | dict(os.environ),
        check=True
    )


@Target(name="all", default=True)
def _all():
    target_test()
    target_build()
    print("All done.")


########
# MAIN #
########
def main():
    for target_name in (sys.argv[1:] if len(sys.argv) > 1 else [None]):
        make(target_name)


if __name__ == '__main__':
    main()
