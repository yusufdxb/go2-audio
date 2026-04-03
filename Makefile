# On ROS 2 machines, system-wide pytest plugins (launch_testing, ament_*)
# auto-load and crash pytest due to hook incompatibilities.
# PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 blocks all entry-point plugins cleanly.
# This is not needed in CI or non-ROS environments.

PYTHON ?= python3

.PHONY: test test-all lint format install install-dev clean

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest tests/ -v --ignore=tests/test_noise_reducer.py

test-all:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest tests/ -v

lint:
	ruff check go2_audio/ tests/
	ruff format --check go2_audio/ tests/

format:
	ruff check --fix go2_audio/ tests/
	ruff format go2_audio/ tests/

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev,ros]"

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
