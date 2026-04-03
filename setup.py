"""Shim for colcon/ament_python which requires setup.py.

All real configuration lives in pyproject.toml.  This file duplicates
entry_points and data_files because ament_python reads setup.py while
pip reads pyproject.toml.  Keep both in sync when changing either.
"""

import os

from setuptools import setup

package_name = "go2_audio"

setup(
    entry_points={
        "console_scripts": [
            "go2-audio-capture = go2_audio.capture:main",
            "go2-audio-node = go2_audio.ros_node:main",
        ],
    },
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name, "launch"),
            ["launch/audio.launch.py"],
        ),
    ],
)
