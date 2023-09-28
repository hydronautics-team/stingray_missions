import asyncio
import logging
import yaml

import rclpy
from rclpy.node import Node

from stingray_missions.core import Mission


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
# logHandler = logging.StreamHandler()
# logger.addHandler(logHandler)

async def ros_loop(node: Node):
    """ROS loop for spinning the node"""
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0)
        # logger.info("Spinning")
        await asyncio.sleep(0.1)


def main():
    rclpy.init()
    event_loop = asyncio.get_event_loop()
    node = rclpy.create_node("async_subscriber")
    with open("configs/default_missions/search_vision.yaml", "r") as f:
        mission_description = yaml.safe_load(f)
    mission = Mission(node, mission_description)

    future = asyncio.wait(
        [ros_loop(node), mission.go()], return_when=asyncio.FIRST_EXCEPTION
    )
    done, _pending = event_loop.run_until_complete(future)
    for task in done:
        task.result()


if __name__ == "__main__":
    main()
