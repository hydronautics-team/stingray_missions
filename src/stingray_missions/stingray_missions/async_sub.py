import asyncio

import rclpy
from std_msgs.msg import String

rclpy.init()
node = rclpy.create_node("async_subscriber")

async def execute():
    print("Node started.")

    async def msg_callback(msg):
        print(f"Message received: {msg}")

    node.create_subscription(String, "topic", msg_callback, 10)
    print("Listening to topic1 topic...")


async def ros_loop():
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0)
        await asyncio.sleep(1e-4)


def main():
    future = asyncio.wait([ros_loop(), execute()])
    asyncio.get_event_loop().run_until_complete(future)


if __name__ == "__main__":
    main()
