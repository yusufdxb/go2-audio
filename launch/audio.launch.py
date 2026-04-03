"""Launch Go2 audio capture node."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_ip", default_value="192.168.123.161"),
            DeclareLaunchArgument("noise_reduce", default_value="false"),
            Node(
                package="go2_audio",
                executable="go2-audio-node",
                name="go2_audio_node",
                parameters=[
                    {
                        "robot_ip": LaunchConfiguration("robot_ip"),
                        "noise_reduce": LaunchConfiguration("noise_reduce"),
                    }
                ],
                output="screen",
            ),
        ]
    )
