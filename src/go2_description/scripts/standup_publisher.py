#!/usr/bin/env python3
"""平滑地从当前姿态插值到站立姿态 (hip 0.0 / thigh 0.67 / calf -1.3)。

订阅当前 /joint_states 起始值，向位置控制器发送渐变指令。
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray

JOINTS = [
    'FL_hip_joint', 'FL_thigh_joint', 'FL_calf_joint',
    'FR_hip_joint', 'FR_thigh_joint', 'FR_calf_joint',
    'RL_hip_joint', 'RL_thigh_joint', 'RL_calf_joint',
    'RR_hip_joint', 'RR_thigh_joint', 'RR_calf_joint',
]
STAND = [0.0, 0.67, -1.3] * 4
CMD_TOPIC = '/go2_position_controller/commands'
RATE = 50.0          # Hz
DURATION = 3.0       # 从当前姿态到站姿的插值时长（秒）


class StandupNode(Node):
    def __init__(self):
        super().__init__('standup_publisher')
        self.pub = self.create_publisher(Float64MultiArray, CMD_TOPIC, 10)
        self.start = None
        self.t = 0.0
        # 等第一条 /joint_states 作为起始姿态
        self.sub = self.create_subscription(
            JointState, '/joint_states', self.on_js, 10)
        self.get_logger().info('等待 /joint_states ...')

    def on_js(self, msg):
        if self.start is not None:
            return
        pos = {n: p for n, p in zip(msg.name, msg.position)}
        if not all(j in pos for j in JOINTS):
            return
        self.start = [pos[j] for j in JOINTS]
        self.get_logger().info(f'起始姿态已获取，{DURATION}s 后到达站姿')
        self.timer = self.create_timer(1.0 / RATE, self.step)

    def step(self):
        self.t += 1.0 / RATE
        s = min(self.t / DURATION, 1.0)
        # 平滑（smoothstep）
        s = s * s * (3 - 2 * s)
        target = [a + (b - a) * s for a, b in zip(self.start, STAND)]
        m = Float64MultiArray()
        m.data = target
        self.pub.publish(m)
        if self.t >= DURATION + 1.0:  # 到位后再保持 1 秒然后退出
            self.get_logger().info('站立完成')
            raise SystemExit(0)


def main():
    rclpy.init()
    node = StandupNode()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
