# Go2 四足机器人 Gazebo + RViz 仿真（ROS 2 Humble）

基于 Unitree Go2 官方 URDF 的 ROS 2 / Gazebo Classic 仿真工程：一键启动无界面物理仿真（gzserver）+ RViz 可视化，机器人自动落地并平滑站立，附带键盘交互控制脚本，以及一个可用 `world` 参数加载的楼道环境示例。

适配环境：**Ubuntu 22.04 / ROS 2 Humble / Gazebo Classic 11**（物理机或 VirtualBox 虚拟机均可，虚拟机中 gzclient 无法渲染，故采用 gzserver + RViz2 方案，物理仿真功能完整）。

## 仓库结构

```
.
├── src/
│   └── go2_description/        # colcon 功能包（ament_cmake）
│       ├── urdf/               # Go2 URDF（含 ros2_control 块 + gazebo_ros2_control 插件）
│       ├── dae/  meshes/       # 外观模型
│       ├── config/             # controller_manager 配置（go2_controllers.yaml）
│       ├── launch/             # go2_standup.launch.py 一键启动
│       └── scripts/            # standup_publisher.py 平滑站立 / go2_keyboard.py 键盘控制
└── room/                       # Building Editor 楼道模型 + room.world 世界文件
```

## 一、安装依赖

```bash
sudo apt update
sudo apt install ros-humble-gazebo-ros-pkgs \
                 ros-humble-gazebo-ros2-control \
                 ros-humble-joint-state-broadcaster \
                 ros-humble-ros2-controllers
```

## 二、编译

```bash
mkdir -p ~/go2_ws/src
cp -r <本仓库>/src/go2_description ~/go2_ws/src/
cd ~/go2_ws
colcon build --packages-select go2_description --symlink-install
source install/setup.bash
```

> 使用 `--symlink-install` 后，URDF / yaml / launch / 脚本改动**免重编译**。
> 每个新终端都需要：`source /opt/ros/humble/setup.bash && source ~/go2_ws/install/setup.bash`

## 三、启动仿真并站立

**终端 1 —— 仿真：**

```bash
ros2 launch go2_description go2_standup.launch.py
```

约 15 秒后自动完成落地 + 平滑站立（3 秒插值到官方站姿：hip 0.0 / thigh 0.67 / calf -1.3）。

加载自定义世界（楼道示例，模型在本仓库 `room/` 下，先把其父目录拷到任意固定路径，例如 `~/room`）：

```bash
cp -r <本仓库>/room ~/room
ros2 launch go2_description go2_standup.launch.py world:=~/room/room.world x:=0.65 y:=-1.34 z:=0.25
```

launch 参数：`world`（世界文件路径）、`x` `y` `z` `yaw`（出生位姿，默认 0.5m 空投）。

**终端 2 —— RViz 观看：**

```bash
rviz2
# Add → RobotModel → Description Topic 选 /robot_description
# 左上 Fixed Frame 设为 odom
```

**终端 3 —— 键盘控制：**

```bash
ros2 run go2_description go2_keyboard.py
```

| 按键 | 动作 |
|------|------|
| `w` / `s` | 蹲下 / 站起 |
| `a` / `d` | 向左 / 向右倾斜 |
| `q` / `e` | 后仰 / 前倾 |
| `空格` | 回标准站姿 |
| `Ctrl+C` | 退出 |

所有动作经 50Hz 限速插值，平滑无瞬移。

## 四、常用命令

```bash
ros2 control list_controllers          # 确认 joint_state_broadcaster / go2_position_controller 为 active
ros2 topic echo /joint_states --once   # 关节角（thigh≈0.67, calf≈-1.3 即标准站姿）
ros2 topic echo /model_states --once   # 机器人世界坐标（需世界文件含 gazebo_ros_state 插件）
```

翻车救援（瞬移回出生点并摆正）：

```bash
ros2 service call /gazebo/set_entity_state gazebo_msgs/srv/SetEntityState \
  "{state: {name: go2, pose: {position: {x: 0.65, y: -1.34, z: 0.4}, orientation: {w: 1.0}}}}"
```

## 五、踩坑记录

1. **虚拟机里 gzclient 必僵死**（VirtualBox 显卡兼容性）→ 用 gzserver 无界面跑物理 + RViz2 看画面，功能不缺。
2. **`spawn_entity` 的 `-topic` 参数在 Humble 有 lxml bug** → 必须用 `-file` 指定 URDF 文件。
3. **报 "no ros2_control tag"** → 多为残留的旧 `robot_state_publisher` 进程顶占了同名节点，插件拿到旧 URDF。启动前先 `pkill -f gzserver; pkill -f robot_state_publisher`。
4. **报 "Loader for controller ... not found"** → 未安装 `joint-state-broadcaster` / `ros2-controllers`。
5. **`ros2 run` 报 "No executable found"** → 脚本缺执行权限：`chmod +x src/go2_description/scripts/*.py`。
6. **一次性发位置指令会瞬移** → JointGroupPositionController 无内部插值，平滑动作需连续发中间目标（脚本已内置）。
7. **落地偶发翻倒且乱蹬滑走** → 用上面的 `set_entity_state` 拉回；出生高度 `z` 建议 0.25 左右。
8. **`libgazebo_ros_state.so` 只能写成 world 插件**（放进 .world 文件），`-s` 方式加载会报 incorrect plugin type；此时话题名是 `/model_states`（无 `/gazebo` 前缀）。
9. **自定义模型找不到（model://xxx）** → 把模型目录的**父目录**加入 `GAZEBO_MODEL_PATH`（本工程 launch 已自动处理 `~/room` 的父目录）。

## 六、技术要点

- **控制架构**：Gazebo Classic + `gazebo_ros2_control`，硬件接口为 12 关节 position 指令 + position/velocity/effort 状态；`joint_state_broadcaster` 发布 `/joint_states`，`go2_position_controller`（JointGroupPositionController，500Hz）接收 `/go2_position_controller/commands`。
- **站立流程**：launch 内定时器编排 gzserver → spawn（4s）→ 加载控制器（7s/9s）→ 站立节点（11s），站立节点取当前姿态 3 秒平滑插值到站姿后退出。
- **房间模型**：`room/model.sdf` 由 Gazebo Building Editor 生成；`room.world` 引用 `model://room` 并注册 `gazebo_ros_state` 插件以提供位姿查询/瞬移服务。
