import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('go2_description')

    # 读取 URDF
    urdf_file = os.path.join(pkg_share, 'urdf', 'go2_description.urdf')
    with open(urdf_file, 'r') as f:
        robot_description = f.read()

    gazebo_share = get_package_share_directory('gazebo_ros')

    # 先只启动服务端（无界面），加载 ROS 接口插件
    gzserver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_share, 'launch', 'gzserver.launch.py')),
        launch_arguments={'verbose': 'true',
                          'init': 'true',
                          'factory': 'true'}.items(),
    )

    # 发布 TF 与 /robot_description
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description,
                     'use_sim_time': True}],
        output='screen',
    )

    # 延迟 4 秒后把 Go2 送进服务端（Humble 的 spawn_entity.py 用 -topic
    # 会因 XML 声明头解析失败，所以直接传 URDF 文件路径）
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

    # 延迟 14 秒后启动图形界面：此时模型已插入完成，
    # 规避 VirtualBox 下 gzclient 插入模型时的 futex 死锁
    gzclient = TimerAction(
        period=14.0,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(gazebo_share, 'launch', 'gzclient.launch.py')),
            launch_arguments={'verbose': 'true'}.items(),
        )],
    )

    return LaunchDescription([
        gzserver,
        robot_state_publisher,
        spawn_entity,
        gzclient,
    ])
