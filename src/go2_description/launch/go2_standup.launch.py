import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def launch_setup(context, *args, **kwargs):
    pkg_share = get_package_share_directory('go2_description')

    urdf_file = os.path.join(pkg_share, 'urdf', 'go2_description.urdf')
    controllers_file = os.path.join(pkg_share, 'config', 'go2_controllers.yaml')

    # URDF 是纯文本，无法用 xacro 替换路径：把占位符替换成控制器 yaml 绝对路径，
    # 生成临时 URDF 供 robot_state_publisher 和 spawn 使用
    with open(urdf_file, 'r') as f:
        robot_description = f.read()
    processed_urdf = robot_description.replace('GO2_CONTROLLERS_YAML', controllers_file)
    urdf_tmp = '/tmp/go2_sim.urdf'
    with open(urdf_tmp, 'w') as f:
        f.write(processed_urdf)

    world = LaunchConfiguration('world').perform(context)
    spawn_x = LaunchConfiguration('x').perform(context)
    spawn_y = LaunchConfiguration('y').perform(context)
    spawn_z = LaunchConfiguration('z').perform(context)
    spawn_yaw = LaunchConfiguration('yaw').perform(context)

    # 无界面 Gazebo 服务端；world 参数非空时加载自定义世界
    # 注意：model_states 话题由 room.world 里的 libgazebo_ros_state.so world 插件提供，
    # -s 方式加载会报 incorrect plugin type，故不在这里加
    gz_cmd = ['gzserver', '--verbose',
              '-s', 'libgazebo_ros_init.so',
              '-s', 'libgazebo_ros_factory.so']
    if world:
        world_path = os.path.abspath(os.path.expanduser(world))
        if not os.path.isfile(world_path):
            raise RuntimeError('world 文件不存在: %s' % world_path)
        gz_cmd.append(world_path)
    gzserver = ExecuteProcess(
        cmd=gz_cmd, output='screen',
        # 让 model://room 等自定义模型可被 Gazebo 找到
        additional_env={'GAZEBO_MODEL_PATH': '/home/zjk:' + os.environ.get(
            'GAZEBO_MODEL_PATH', '/usr/share/gazebo-11/models')},
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description,
                     'use_sim_time': True}],
        output='screen',
    )

    spawn_args = ['-entity', 'go2', '-file', urdf_tmp,
                  '-x', spawn_x, '-y', spawn_y, '-z', spawn_z, '-Y', spawn_yaw]

    # 延迟 4 秒注入 Go2
    spawn_entity = TimerAction(
        period=4.0,
        actions=[Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            arguments=spawn_args,
            output='screen',
        )],
    )

    # 延迟 7 秒加载关节状态广播器
    spawn_jsb = TimerAction(
        period=7.0,
        actions=[Node(
            package='controller_manager',
            executable='spawner',
            arguments=['joint_state_broadcaster',
                       '--controller-manager', '/controller_manager'],
            output='screen',
        )],
    )

    # 延迟 9 秒加载位置控制器
    spawn_pos = TimerAction(
        period=9.0,
        actions=[Node(
            package='controller_manager',
            executable='spawner',
            arguments=['go2_position_controller',
                       '--controller-manager', '/controller_manager'],
            output='screen',
        )],
    )

    # 延迟 11 秒开始平滑站立
    standup = TimerAction(
        period=11.0,
        actions=[Node(
            package='go2_description',
            executable='standup_publisher.py',
            output='screen',
        )],
    )

    return [gzserver, robot_state_publisher, spawn_entity, spawn_jsb, spawn_pos, standup]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='',
                              description='自定义 Gazebo 世界文件路径（.world/.sdf），留空用 empty'),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('y', default_value='0.0'),
        DeclareLaunchArgument('z', default_value='0.5'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        OpaqueFunction(function=launch_setup),
    ])
