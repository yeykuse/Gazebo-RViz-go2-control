import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('go2_description')

    # 读取 URDF
    urdf_file = os.path.join(pkg_share, 'urdf', 'go2_description.urdf')
    with open(urdf_file, 'r') as f:
        robot_description = f.read()

    # 无界面 Gazebo 服务端（带 ROS 接口插件）
    gzserver = ExecuteProcess(
        cmd=['gzserver', '--verbose',
             '-s', 'libgazebo_ros_init.so',
             '-s', 'libgazebo_ros_factory.so'],
        output='screen',
    )

    # 发布 TF 与 /robot_description
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description,
                     'use_sim_time': True}],
        output='screen',
    )

    # 延迟 4 秒注入 Go2
    spawn_entity = TimerAction(
        period=4.0,
        actions=[Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            arguments=['-entity', 'go2',
                       '-file', urdf_file,
                       '-z', '0.5'],
            output='screen',
        )],
    )

    return LaunchDescription([
        gzserver,
        robot_state_publisher,
        spawn_entity,
    ])
