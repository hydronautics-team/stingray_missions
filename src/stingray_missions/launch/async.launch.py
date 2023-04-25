from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='stingray_missions',
            executable='pub',
            name='pub'
        ),
        Node(
            package='stingray_missions',
            executable='async_sub',
            name='async_sub'
        )
    ])