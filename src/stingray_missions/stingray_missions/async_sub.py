from transitions.extensions.asyncio import AsyncMachine
import asyncio
import json
from pathlib import Path
import yaml
import logging
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TopicEvent:
    def __init__(self, trigger_fn, topic: str, data: str, trigger: str, count: int = 0):
        self.trigger_fn = trigger_fn
        self.topic = topic
        self.data = data
        self.trigger = trigger
        self.count = count

        self.subsctiption = None

        self._counter = 0

    async def subscribe(self, node: Node):
        self.subsctiption = node.create_subscription(String, self.topic, self.msg_callback, 10)
        logger.info(f"Subscribed to {self.topic}")

    async def unsubscribe(self, node: Node):
        node.destroy_subscription(self.subsctiption)
        logger.info(f"Unsubscribed from {self.topic}")

    async def msg_callback(self, msg: String):
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
        self.node = node
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.register_machine()
        self.register_events()

    def register_machine(self):
        self.machine = AsyncMachine(
            model=self,
            states=["START", "FINISH"],
            transitions=[["abort", "*", "FINISH"]],
            initial="START",
            auto_transitions=False,
            after_state_change="after_state_change",
            before_state_change="before_state_change",
        )
        self.machine.add_states(self.config["states"])
        self.machine.add_transitions(self.config["transitions"])

    async def on_enter_FINISH(self):
        for event in self.events.values():
            await event.unsubscribe(self.node)
        logger.info("Mission finished")

    async def after_state_change(self):
        if self.state in self.events:
            await self.events[self.state].subscribe(self.node)
        logger.info(f"{self.state} started")

    async def before_state_change(self):
        if self.state in self.events:
            await self.events[self.state].unsubscribe(self.node)
        logger.info(f"{self.state} ended")

    def register_events(self):
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
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0)
        logger.info("Spinning")
        await asyncio.sleep(0.5)


def main():
    rclpy.init()
    node = rclpy.create_node("async_subscriber")
    mission = Mission(node, "configs/mission.yaml")

    future = asyncio.wait([ros_loop(node), mission.go()],  return_when=asyncio.FIRST_EXCEPTION)
    done, _pending = asyncio.get_event_loop().run_until_complete(future)
    for task in done:
        task.result()

if __name__ == "__main__":
    main()
