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


class TopicEvent:
    def __init__(self, trigger_fn, data: str, trigger: str, count: int = 0):
        self.trigger_fn = trigger_fn
        self.data = data
        self.trigger = trigger
        self.count = count

        self._counter = 0

    async def msg_callback(self, msg: String):
        print(f"Message received: {msg}")
        if msg.data == self.data:
            print("yes")
            self._counter += 1
            if self._counter == self.count:
                self._counter = 0
                await self.trigger_fn(self.trigger)
        else:
            self._counter = 0


class Mission:
    def __init__(self, node: Node, missions_pkg: str = "stingray_missions"):
        self.node = node

        config_path = Path("src/stingray_missions/configs/mission.yaml")
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.machine = AsyncMachine(
            model=self,
            states=["start", "finish"],
            transitions=[["abort", "*", "finish"]],
            initial="start",
            auto_transitions=False,
        )
        self.machine.add_states(self.config["states"])
        self.machine.add_transitions(self.config["transitions"])

        self.events: list[TopicEvent] = []
        if self.config["events"]:
            print(self.config["events"])
            self.register_events()

    def register_events(self):
        for event in self.config["events"]:
            print('Trying to register event type: ', event["type"])
            if event["type"] == "TopicEvent":
                self.events.append(
                    TopicEvent(
                        self.trigger,
                        event["data"],
                        event["trigger"],
                        event["count"],
                    )
                )
            else:
                raise ValueError("Event type not supported")
            self.node.create_subscription(
                String, event["topic"], self.events[-1].msg_callback, 10
            )
            print(f"Subscribed to {event['topic']}")


async def ros_loop(node: Node):
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0)
        await asyncio.sleep(1e-4)


def main():
    rclpy.init()
    node = rclpy.create_node("async_subscriber")
    mission = Mission(node)

    future = asyncio.wait([ros_loop(node), mission.go()])
    asyncio.get_event_loop().run_until_complete(future)


if __name__ == "__main__":
    main()
