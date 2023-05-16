from transitions.extensions.asyncio import AsyncMachine
import logging
from rclpy.node import Node
import asyncio

from stingray_missions.event import TopicEvent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Mission(object):
    def __init__(self, loop: asyncio.AbstractEventLoop, node: Node, mission_description: dict):
        """Mission class for executing a mission from a config file"""
        self.loop = loop
        self.node = node
        self.desc = mission_description

        self.name = self.desc["name"]
        self.events: dict[str, TopicEvent] = {}
        self.expiration_timer = None

        self.add_machine()
        self.add_states(self.desc["states"])
        self.add_transitions(self.desc["transitions"])

        logger.info(f"Mission {self.name} created")
        # logger.info(f"States: {self.machine.states}")

    def add_machine(self):
        """Registering the state machine from the config file"""

        self.init_state = 'INIT'
        self.success_state = 'SUCCESS'
        self.failure_state = 'FAILURE'
        self.go_transition = 'go'
        self.abort_transition = 'abort'
        self.reset_transition = 'reset'
        self.timeout_transition = 'timeout'

        self.default_states = [self.init_state,
                               self.success_state, self.failure_state]
        if self.desc["default_transitions"]:
            self.default_transitions = [
                [self.abort_transition, "*", self.failure_state]]
        else:
            self.default_transitions = []

        self.machine = AsyncMachine(
            model=self,
            states=self.default_states,
            transitions=self.default_transitions,
            initial=self.init_state,
            auto_transitions=False,
            after_state_change="execute_state",
            before_state_change="leave_state",
        )

    def add_states(self, states: dict):
        for state, args in states.items():
            self.machine.add_state(f'{state}')
            logger.info(f"Added state {state} : {args}")
            if 'initial' in args and args['initial']:
                self.machine.add_transition(
                    trigger=self.go_transition, source=self.init_state, dest=state)
            if args['event']:
                try:
                    self.add_event(
                        state, self.desc["events"][args['event']])
                except KeyError:
                    logger.error(
                        f"Event {args['event']} not found in events list")

    def add_event(self, state_name: str, args: dict):
        """Registering events from the config file"""
        if args["type"] == "TopicEvent":
            self.events[state_name] = TopicEvent(
                trigger_fn=self.trigger,
                topic=args["topic"],
                data=args["data"],
                trigger=args["trigger"],
                count=args["count"],
            )
            logger.info(f"Added event {state_name}")
        else:
            raise ValueError("Event type not supported")

    def add_transitions(self, transitions: dict):
        for transition in transitions:
            self.machine.add_transition(trigger=transition['trigger'].format(
                go=self.go_transition, abort=self.abort_transition, reset=self.reset_transition, timeout=self.timeout_transition),
                source=transition['source'],
                dest=transition['dest'].format(
                init=self.init_state, success=self.success_state, failure=self.failure_state))

    async def on_enter_FAILURE(self):
        """Executing on entering the FAILURE state"""
        for event in self.events.values():
            await event.unsubscribe(self.node)
        logger.info("Mission failed")

    async def on_enter_SUCCESS(self):
        """Executing on entering the SUCCESS state"""
        for event in self.events.values():
            await event.unsubscribe(self.node)
        logger.info("Mission succeeded")

    async def execute_state(self):
        """Executing as soon as the state is entered"""
        logger.info(f"Executing {self.state}")
        logger.info(f"Transitions: {self.machine.get_triggers(self.state)}")
        try:
            await self.events[self.state].subscribe(self.node)
        except KeyError:
            logger.info(f"No event for state {self.state}")
        try:
            timeout_value = self.desc["states"][self.state]["expire_time"]
            self.expiration_timer = self.node.create_timer(
                timeout_value, self.countdown)
            logger.info(
                f"State {self.state} will expire in {timeout_value} seconds")
        except KeyError:
            logger.info(f"No expiration time for state {self.state}")

        logger.info(f"{self.state} started")

    async def leave_state(self):
        """Executing before leaving the state"""
        try:
            await self.events[self.state].unsubscribe(self.node)
        except KeyError:
            logger.info(f"No event for state {self.state}")
        if self.expiration_timer and not self.expiration_timer.is_ready():
            self.expiration_timer.cancel()
            self.expiration_timer = None
            logger.info(f"Cancel expiration timer for {self.state}")
        logger.info(f"{self.state} ended")

    async def countdown(self):
        """Countdown for the mission"""
        logger.info(
            f"State {self.state} expired. Triggering {self.timeout_transition}")
        await self.trigger(self.timeout_transition)
