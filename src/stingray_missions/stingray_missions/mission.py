from transitions.extensions.asyncio import AsyncMachine
import asyncio
import json
from pathlib import Path
import yaml
# from ament_index_python.packages import get_package_share_directory


class Mission:
    def __init__(self, missions_pkg: str = "stingray_missions"):
        # config_path = Path(get_package_share_directory(missions_pkg)) / "config" / "mission.yaml"
        config_path = Path("src/stingray_missions/configs/mission.yaml")
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        print(self.config)

        self.machine = AsyncMachine(
            model=self,
            states=["start", "finish"],
            transitions=[["stop", "*", "end"]],
            initial="start",
        )
        self.machine.add_states(self.config["states"])
        self.machine.add_transitions(self.config["transitions"])

    def msg_callback(self, msg):
        if msg == "gate":
            self.gate_count += 1
            if self.gate_count == 5:
                # Trigger the state machine "found" to make a transition to end
                pass
        else:
            self.gate_count = 0
