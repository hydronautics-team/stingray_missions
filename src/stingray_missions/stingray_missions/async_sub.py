from transitions.extensions.asyncio import AsyncMachine
import asyncio
import json
from pathlib import Path
import yaml
import logging
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String
from geometry_msgs.msg import Vector3, Twist


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActionClientX(ActionClient):
    feedback_queue = asyncio.Queue()

    async def feedback_cb(self, msg):
        await self.feedback_queue.put(msg)

    async def send_goal_async(self, goal_msg):
        goal_future = super().send_goal_async(
            goal_msg, feedback_callback=self.feedback_cb
        )
        client_goal_handle = await asyncio.ensure_future(goal_future)
        if not client_goal_handle.accepted:
            raise Exception("Goal rejected.")
        result_future = client_goal_handle.get_result_async()
        while True:
            feedback_future = asyncio.ensure_future(self.feedback_queue.get())
            tasks = [result_future, feedback_future]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            if result_future.done():
                result = result_future.result().result
                yield (None, result)
                break
            else:
                feedback = feedback_future.result().feedback
                yield (feedback, None)


class Robot:
    def __init__(self, node: Node):
        """Robot class for executing robot commands:
        Services:
        - set_velocity
        - set_pose
        - set_stabilization
        - set_device
        Actions:
        - move_to
        - explore
        - search
        - center
        - follow
        """
        self.node = node

        self.set_velocity_service = node.create_client(Twist, "set_velocity")
        self.set_pose_service = node.create_client(SetPose, "set_pose")
        self.set_stabilization_service = node.create_client(SetStabilization, "set_stabilization")
        self.set_device_service = node.create_client(SetDevice, "set_device")

    def set_velocity(self, linear: float, angular: float):
        """Set the velocity of the robot"""
        req = Twist()
        req.linear.x = linear
        req.angular.z = angular
        self.set_velocity_service.call_async(req)


class TopicEvent:
    def __init__(self, trigger_fn, topic: str, data: str, trigger: str, count: int = 0):
        """Event class for subscribing to a topic and triggering a transition when a certain message is received"""
        self.trigger_fn = trigger_fn
        self.topic = topic
        self.data = data
        self.trigger = trigger
        self.count = count

        self.subsctiption = None

        self._counter = 0

    async def subscribe(self, node: Node):
        """Subscribing to the topic"""
        self.subsctiption = node.create_subscription(
            String, self.topic, self.msg_callback, 10
        )
        logger.info(f"Subscribed to {self.topic}")

    async def unsubscribe(self, node: Node):
        """Unsubscribing from the topic"""
        node.destroy_subscription(self.subsctiption)
        logger.info(f"Unsubscribed from {self.topic}")

    async def msg_callback(self, msg: String):
        """Callback function for the topic subscription"""
        logger.info(f"Message received: {msg.data}")
        if msg.data == self.data:
            self._counter += 1
            if self._counter == self.count:
                self._counter = 0
                await self.trigger_fn(self.trigger)
        else:
            self._counter = 0


class Mission:
    def __init__(self, node: Node, config_path: str):
        """Mission class for executing a mission from a config file"""
        self.node = node
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.register_machine()
        self.register_events()

    def register_machine(self):
        """Registering the state machine from the config file"""
        self.machine = AsyncMachine(
            model=self,
            states=["START", "FINISH"],
            transitions=[["abort", "*", "FINISH"]],
            initial="START",
            auto_transitions=False,
            after_state_change="execute_state",
            before_state_change="leave_state",
        )
        self.machine.add_states(self.config["states"])
        self.machine.add_transitions(self.config["transitions"])

    async def on_enter_FINISH(self):
        """Executing on entering the FINISH state"""
        for event in self.events.values():
            await event.unsubscribe(self.node)
        logger.info("Mission finished")

    async def execute_state(self):
        """Executing as soon as the state is entered"""
        if self.state in self.events:
            await self.events[self.state].subscribe(self.node)
        logger.info(f"{self.state} started")

    async def leave_state(self):
        """Executing before leaving the state"""
        if self.state in self.events:
            await self.events[self.state].unsubscribe(self.node)
        logger.info(f"{self.state} ended")

    def register_events(self):
        """Registering events from the config file"""
        self.events: dict[str, TopicEvent] = {}
        for event in self.config["events"]:
            if event["type"] == "TopicEvent":
                self.events[event["state"]] = TopicEvent(
                    trigger_fn=self.trigger,
                    topic=event["topic"],
                    data=event["data"],
                    trigger=event["trigger"],
                    count=event["count"],
                )
            else:
                raise ValueError("Event type not supported")


async def ros_loop(node: Node):
    """ROS loop for spinning the node"""
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0)
        logger.info("Spinning")
        await asyncio.sleep(0.5)


def main():
    rclpy.init()
    node = rclpy.create_node("async_subscriber")
    mission = Mission(node, "configs/mission.yaml")

    future = asyncio.wait(
        [ros_loop(node), mission.go()], return_when=asyncio.FIRST_EXCEPTION
    )
    done, _pending = asyncio.get_event_loop().run_until_complete(future)
    for task in done:
        task.result()


if __name__ == "__main__":
    main()
