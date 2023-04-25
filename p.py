from transitions.extensions.asyncio import AsyncMachine
import asyncio
import json
from pathlib import Path
import yaml
import logging

logging.basicConfig(level=logging.INFO)

class TopicEvent:
    def __init__(self, trigger_fn, data: str, trigger: str, count: int = 0):
        self.data = data
        self.count = count
        self.trigger = trigger
        self.trigger_fn = trigger_fn

        self._counter = 0

    async def msg_callback(self, msg: str):
        print(f"Message received: {msg}")
        if msg == self.data:
            print('yes')
            self._counter += 1
            if self._counter == self.count:
                self._counter = 0
                await self.trigger_fn(self.trigger)
        else:
            self._counter = 0


class Mission:
    def __init__(self, missions_pkg: str = "stingray_missions"):
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

        self.events: TopicEvent = []
        if self.config["events"]:
            print(self.config["events"])
            for event in self.config["events"]:
                if event["type"] == "TopicEvent":
                    self.events.append(
                        TopicEvent(self.trigger, event["data"], event["trigger"], event["count"])
                    )
                else:
                    raise ValueError("Event type not supported")


async def msg_loop(mission_obj: Mission):
    mission_obj.events
    while True:
        for event in mission_obj.events:
            await event.msg_callback("gate")
        await asyncio.sleep(1)


def main():
    mission = Mission()
    future = asyncio.wait([msg_loop(mission), mission.go()])
    asyncio.get_event_loop().run_until_complete(future)


if __name__ == "__main__":
    asyncio.run(main())
