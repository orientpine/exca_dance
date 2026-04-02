#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, Header, Float32
from sensor_msgs.msg import NavSatFix
from geometry_msgs.msg import TwistWithCovariance
from msg_excavator_kine_interface.msg import KineMsg
from msg_gps_interface.msg import GPSMsgAtt, GPSMsg
import sys
import signal

from .config_loader import get_shared_value, load_shared_parameters, load_yaml_file

class KinePublisherNode(Node):
    """
    Kine Publisher 노드
    - 단순화된 토픽 취합 및 재발행 노드
    - inclinometer_node.py에서 계산된 joint 값들을 수신
    - KineMsg 형식으로 통합하여 발행
    """
    
    def __init__(self):
        super().__init__('kine_publisher_node')

        # 설정 파일 로드
        self.config = self.load_config()
        self.shared_config = load_shared_parameters()
        shared_topics = self.shared_config.get('topics', {})
        shared_frames = self.shared_config.get('frame_ids', {})
        default_publish_rate = get_shared_value(['publish_rates', 'kine_publisher'], 10.0)
        self.kine_topic = shared_topics.get('kine_output', '/kine_data')
        self.base_link_frame = shared_frames.get('base_link', 'base_link')
        
        # 발행 주기 파라미터 (Hz)
        self.declare_parameter('publish_rate', default_publish_rate)
        
        # 콘솔 출력 제어 파라미터 추가
        self.declare_parameter('enable_console_output', True)
        
        # 발행 주기 가져오기
        publish_rate = self.get_parameter('publish_rate').get_parameter_value().double_value
        
        # 콘솔 출력 여부 가져오기
        self.enable_console_output = self.get_parameter('enable_console_output').get_parameter_value().bool_value

        # 계산된 joint 값들을 구독 (inclinometer_node.py에서 발행)
        self.joint_boom_subscription = self.create_subscription(
            Float32MultiArray,
            shared_topics.get('joint_boom', '/excavator/sensors/joint_boom'),
            self.joint_boom_callback,
            10
        )
        self.joint_arm_subscription = self.create_subscription(
            Float32MultiArray,
            shared_topics.get('joint_arm', '/excavator/sensors/joint_arm'),
            self.joint_arm_callback,
            10
        )
        self.joint_bucket_subscription = self.create_subscription(
            Float32MultiArray,
            shared_topics.get('joint_bucket', '/excavator/sensors/joint_bucket'),
            self.joint_bucket_callback,
            10
        )
        
        # 기존 센서 데이터 구독 (단순 취합용)
        self.swing_subscription = self.create_subscription(
            Float32,
            shared_topics.get('swing_angle', '/excavator/sensors/swing_angle'),
            self.swing_callback,
            10
        )
        self.gnss_position_subscription = self.create_subscription(
            NavSatFix,
            shared_topics.get('gnss_position', '/excavator/sensors/gnss_position'),
            self.gnss_position_callback,
            10
        )
        self.gnss_velocity_subscription = self.create_subscription(
            TwistWithCovariance,
            shared_topics.get('gnss_velocity', '/excavator/sensors/gnss_velocity'),
            self.gnss_velocity_callback,
            10
        )
        
        # GPS attitude 정보를 위한 구독자
        self.gps_attitude_subscription = self.create_subscription(
            GPSMsgAtt,
            shared_topics.get('gps_attitude', '/excavator/sensors/gps_attitude'),
            self.gps_attitude_callback,
            10
        )
        
        # KineMsg 퍼블리셔
        self.kine_publisher = self.create_publisher(KineMsg, self.kine_topic, 10)

        # 타이머 설정 (일정 주기로 발행)
        timer_period = 1.0 / publish_rate
        self.timer = self.create_timer(timer_period, self.timer_callback)

        # 계산된 joint 값 저장용 (단순 취합)
        self.joint_boom = 0.0
        self.joint_arm = 0.0
        self.joint_bucket = 0.0
        
        # GPS 데이터 저장용
        self.gps_pitch = 0.0
        self.gps_heading = 0.0
        self.gps_roll = 0.0
        self.gps_lat = 0.0
        self.gps_lon = 0.0
        self.gps_alt = 0.0
        
        # Swing angle 저장용
        self.swing_angle = 0.0

        # 콘솔 첫 출력 여부
        self.first_print = True

        # 노드 시작 로그
        self.get_logger().info('Kine Publisher Node (단순화 버전)가 시작되었습니다.')
        self.get_logger().info(f'발행 주기: {publish_rate} Hz')
        self.get_logger().info('계산된 joint 값들을 수신하여 KineMsg로 재발행합니다.')
        
        # 빈 줄 출력
        print()

    def load_config(self):
        """설정 파일 로드"""
        try:
            config = load_yaml_file('kine_publisher_config.yaml')
            return config or {}
        except Exception as e:
            self.get_logger().warning(f'설정 파일 로드 실패: {str(e)} - 기본값 사용')
            return {}

    def joint_boom_callback(self, msg):
        """계산된 Boom joint 값 콜백 (단순 취합)"""
        if len(msg.data) >= 1:
            self.joint_boom = msg.data[0]

    def joint_arm_callback(self, msg):
        """계산된 Arm joint 값 콜백 (단순 취합)"""
        if len(msg.data) >= 1:
            self.joint_arm = msg.data[0]

    def joint_bucket_callback(self, msg):
        """계산된 Bucket joint 값 콜백 (단순 취합)"""
        if len(msg.data) >= 1:
            self.joint_bucket = msg.data[0]

    def swing_callback(self, msg):
        """Swing angle 데이터 콜백 (단순 취합)"""
        self.swing_angle = msg.data

    def gnss_position_callback(self, msg):
        """GNSS 위치 데이터 콜백 (단순 취합)"""
        self.gps_lat = msg.latitude
        self.gps_lon = msg.longitude
        self.gps_alt = msg.altitude

    def gnss_velocity_callback(self, msg):
        """GNSS 속도 데이터 콜백 (현재는 사용하지 않음)"""
        pass

    def gps_attitude_callback(self, msg):
        """GPS attitude 데이터 콜백 (단순 취합)"""
        self.gps_pitch = msg.pitch
        self.gps_roll = msg.roll
        self.gps_heading = msg.heading

    def timer_callback(self):
        """타이머 콜백 - 일정 주기로 KineMsg 발행"""
        self.process_and_publish()

    def process_and_publish(self):
        """데이터 취합 및 KineMsg 발행 (단순화된 버전)"""
        try:
            # KineMsg 생성
            kine_msg = KineMsg()
            
            # Header 설정
            kine_msg.header = Header()
            kine_msg.header.stamp = self.get_clock().now().to_msg()
            kine_msg.header.frame_id = self.base_link_frame

            # 계산된 Joint 값 설정 (단순 취합)
            kine_msg.joint_boom = self.joint_boom
            kine_msg.joint_arm = self.joint_arm
            kine_msg.joint_bucket = self.joint_bucket
            kine_msg.joint_swing = self.swing_angle
            kine_msg.joint_track = 0.0
            
            # 위치 및 자세 정보 (기본값)
            kine_msg.bkt_pos_x = 0.0
            kine_msg.bkt_pos_y = 0.0
            kine_msg.bkt_pos_z = 0.0
            kine_msg.bkt_lat = 0.0
            kine_msg.bkt_lon = 0.0
            kine_msg.bkt_height = 0.0
            
            kine_msg.base_pos_x = 0.0
            kine_msg.base_pos_y = 0.0
            kine_msg.base_pos_z = 0.0
            
            # GPS 데이터 설정 (단순 취합)
            kine_msg.base_lat = self.gps_lat
            kine_msg.base_lon = self.gps_lon
            kine_msg.base_height = self.gps_alt
            kine_msg.roll = self.gps_roll
            kine_msg.pitch = self.gps_pitch
            kine_msg.yaw = 0.0
            kine_msg.gnss_heading = self.gps_heading

            # 메시지 발행
            self.kine_publisher.publish(kine_msg)

            # 콘솔 갱신 출력
            self.refresh_console(kine_msg)

        except Exception as e:
            self.get_logger().error(f'KineMsg 발행 오류: {str(e)}')

    def refresh_console(self, kine_msg):
        """콘솔 덮어쓰기 출력 (파라미터로 제어)"""
        # 콘솔 출력이 비활성화된 경우 출력하지 않음
        if not self.enable_console_output:
            return
            
        if not self.first_print:
            # 이전 10줄 위로 이동해 지우기
            sys.stdout.write("\033[10A")
            for _ in range(10):
                sys.stdout.write("\033[K")
        else:
            self.first_print = False

        # 실제 송신되는 KineMsg의 값들 출력
        print(f"Joint Boom (계산됨):      {kine_msg.joint_boom:.4f}")
        print(f"Joint Arm (계산됨):       {kine_msg.joint_arm:.4f}")
        print(f"Joint Bucket (계산됨):    {kine_msg.joint_bucket:.4f}")
        print(f"Joint Swing:              {kine_msg.joint_swing:.4f}")
        print(f"GPS Pitch:                {self.gps_pitch:.4f}")
        print(f"GPS Heading:              {self.gps_heading:.4f}")
        print(f"GPS Roll:                 {self.gps_roll:.4f}")
        print(f"GPS Lat:                  {self.gps_lat:.8f}")
        print(f"GPS Lon:                  {self.gps_lon:.8f}")
        print(f"GPS Alt:                  {self.gps_alt:.4f}")
        sys.stdout.flush()

    def destroy_node(self):
        """노드 종료 시 호출되는 함수"""
        try:
            self.get_logger().info('Shutting down Kine Publisher Node...')
            super().destroy_node()
            self.get_logger().info('Kine Publisher Node shutdown completed')
        except Exception as e:
            self.get_logger().error(f'Error during node destruction: {str(e)}')

def signal_handler(signum, frame):
    """시그널 핸들러"""
    print(f"\nReceived signal {signum}. Cleaning up...")
    sys.exit(0)

def main(args=None):
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    rclpy.init(args=args)
    node = KinePublisherNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Shutting down...")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
    finally:
        try:
            node.destroy_node()
        except:
            pass
        try:
            rclpy.shutdown()
        except:
            pass

if __name__ == '__main__':
    main() 