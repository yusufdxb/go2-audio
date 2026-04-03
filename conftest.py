"""Root conftest — gives a helpful error when ROS pytest plugins interfere.

On machines with ROS 2 installed, system-wide pytest plugins
(launch_testing, ament_*) register hooks that crash modern pytest.
If you see a PluginValidationError, run tests via:

    make test

or:

    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/ -v
"""

import os
import sys


def pytest_configure(config):
    # If we got this far, plugins loaded successfully — nothing to do.
    # This hook exists so the docstring above appears when pytest
    # introspects conftest.py, and to catch the case where someone
    # imports conftest directly.
    pass


# If ROS plugins are present and the env var is not set, warn early.
# This runs at import time, before pytest's plugin validation.
if "PYTEST_DISABLE_PLUGIN_AUTOLOAD" not in os.environ:
    try:
        import launch_testing  # noqa: F401

        print(
            "WARNING: ROS 2 pytest plugins detected. If pytest crashes, run:\n"
            "  make test\n"
            "or:\n"
            "  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/ -v\n",
            file=sys.stderr,
        )
    except ImportError:
        pass
