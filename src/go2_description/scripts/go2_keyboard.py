#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Go2 键盘姿态控制：w/s 蹲伏，a/d 左右倾斜，q/e 前后俯仰，空格回站姿。

所有目标变化都经过限速插值，以 50Hz 连续发布到
/go2_position_controller/commands，因此动作平滑不会瞬移。
"""

import math
import select
import sys
import termios
import tty

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

# 关节顺序: FL FR RL RR 各 {hip, thigh, calf}
JOINT_NAMES = [
    'FL_hip_joint', 'FL_thigh_joint', 'FL_calf_joint',
    'FR_hip_joint', 'FR_thigh_joint', 'FR_calf_joint',
    'RL_hip_joint', 'RL_thigh_joint', 'RL_calf_joint',
    'RR_hip_joint', 'RR_thigh_joint', 'RR_calf_joint',
]

# 官方站姿
STAND = {
    'thigh': 0.67, 'calf': -1.3,
    'hip': 0.0,
    # 蹲伏极限
    'thigh_down': 1.2, 'calf_down': -2.3,
    # 倾斜/俯仰幅度
    'tilt': 0.25, 'pitch': 0.3,
}
# 限速（rad/s）与发布频率
MAX_JOINT_SPEED = 1.2
RATE_HZ = 50.0

HELP = """================ Go2 键盘控制 ================
 w / s   : 蹲下 / 站起（连续按住或多次点按）
 a / d   : 向左 / 向右倾斜
 q / e   : 后仰 / 前倾
 空格     : 恢复标准站姿
 ctrl+c  : 退出
=============================================="""


class KeyboardPoseNode(Node):

    def __init__(self):
        super().__init__('go2_keyboard_pose')
        self.pub = self.create_publisher(
            Float64MultiArray, '/go2_position_controller/commands', 10)

        # 当前指令状态（12 关节），从标准站姿出发
        self.cur = [0.0, STAND['thigh'], STAND['calf']] * 4
        # 目标调节量
        self.crouch = 0.0   # 0~1
        self.tilt = 0.0     # -1~1
        self.pitch = 0.0    # -1~1

        self.period = 1.0 / RATE_HZ
        self.timer = self.create_timer(self.period, self.tick)
        self.get_logger().info(HELP)

    # 根据调节量计算 12 关节目标
    def compute_target(self):
        t = STAND
        thigh = t['thigh'] + self.crouch * (t['thigh_down'] - t['thigh'])
        calf = t['calf'] + self.crouch * (t['calf_down'] - t['calf'])
        targets = []
        for leg, hip_s in (('FL', 1.0), ('FR', -1.0), ('RL', 1.0), ('RR', -1.0)):
            hip = t['hip'] + self.tilt * t['tilt'] * hip_s
            th = thigh
            # 俯仰：前腿与后腿反向偏移，产生抬头/低头效果
            front = leg in ('FL', 'FR')
            th += self.pitch * t['pitch'] * (1.0 if front else -1.0)
            ca = calf - self.pitch * t['pitch'] * (1.0 if front else -1.0)
            targets += [hip, th, ca]
        return targets

    def tick(self):
        self.read_keys()
        target = self.compute_target()
        # 限速插值：每 tick 最多移动 MAX_JOINT_SPEED * period
        step = MAX_JOINT_SPEED * self.period
        moved = False
        for i in range(12):
            diff = target[i] - self.cur[i]
            if abs(diff) > 1e-6:
                moved = True
            self.cur[i] += max(-step, min(step, diff))
        msg = Float64MultiArray()
        msg.data = self.cur
        self.pub.publish(msg)
        if moved:
            self.get_logger().debug('crouch=%.2f tilt=%.2f pitch=%.2f'
                                    % (self.crouch, self.tilt, self.pitch))

    def read_keys(self):
        while True:
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if not r:
                return
            ch = sys.stdin.read(1)
            if ch == 'w':
                self.crouch = min(1.0, self.crouch + 0.15)
            elif ch == 's':
                self.crouch = max(0.0, self.crouch - 0.15)
            elif ch == 'a':
                self.tilt = min(1.0, self.tilt + 0.2)
            elif ch == 'd':
                self.tilt = max(-1.0, self.tilt - 0.2)
            elif ch == 'q':
                self.pitch = min(1.0, self.pitch + 0.2)
            elif ch == 'e':
                self.pitch = max(-1.0, self.pitch - 0.2)
            elif ch == ' ':
                self.crouch = 0.0
                self.tilt = 0.0
                self.pitch = 0.0
            elif ch == '\x03':  # ctrl+c
                raise KeyboardInterrupt


def main():
    rclpy.init()
    node = KeyboardPoseNode()
    # 终端切 raw 模式，按键免回车
    old_attr = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_attr)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        print('\n已退出键盘控制')


if __name__ == '__main__':
    main()
