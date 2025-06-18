SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -ecu

PWD := $(realpath $(dir $(abspath $(firstword $(MAKEFILE_LIST)))))

.DEFAULT_GOAL := default
.PHONY: default
default:
	@echo "No target specified."
	@echo "Using default target."

test:
	@echo "Run tests."
	cd "$(PWD)" && uv run --module unittest discover --start-directory 'tests' --pattern 'test_*.py' -v