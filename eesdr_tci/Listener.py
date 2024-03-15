"""The listener module contains the main Listener class which interacts with the TCI server."""

import asyncio
import websockets
from . import tci

class Listener:
    """The Listener class interacts with the TCI server by listening for parameter updates and
    maintaining a cache of the current state.  A sender task passes formatted command strings
    to the server.  Parameter and data stream callbacks can be registered to be notified of changes
    of interest as many commands may be ignorable in certain use cases.
    """

    def __init__(self, uri):
        self.uri = uri
        self._tci_params = {"system":{}, "receivers":{}}
        self._tci_param_listeners = {}
        self._tci_data_listeners = {}
        self._tci_send = None
        self._listen_task = None
        self._sender_task = None
        self._connected_event = None
        self._ready_event = None

    @staticmethod
    def _convert_type(val):
        """Converts a string to int, float, or bool if possible, but returning the string if not."""
        try:
            return int(val)
        except (ValueError, TypeError):
            pass

        try:
            return float(val)
        except (ValueError, TypeError):
            pass

        if val.upper() == "TRUE":
            return True
        if val.upper() == "FALSE":
            return False

        return val

    def add_param_listener(self, param, callback):
        """Registers a callback to be notified of a particular parameter change.

        The callback signature is (param_name, rx, sub_rx, params).
        The special param "*" can be used to register a listener for all parameters.
        """
        if param not in self._tci_param_listeners:
            self._tci_param_listeners[param] = []
        l = self._tci_param_listeners[param]
        if callback not in l:
            l += [callback]

    def remove_param_listener(self, param, callback):
        """Removes a parameter callback from the notification list"""
        l = self._tci_param_listeners[param]
        if callback in l:
            l.remove(callback)

    def add_data_listener(self, data_type, callback):
        """Registers a callback to be notified when a particular type of data packet is received.

        The callback signature is (packet).
        The special data_type "*" can be used to register a listener for all data types.
        """
        if data_type not in self._tci_data_listeners:
            self._tci_data_listeners[data_type] = []
        l = self._tci_data_listeners[data_type]
        if callback not in l:
            l += [callback]

    def remove_data_listener(self, data_type, callback):
        """Removes a data callback from the notification list."""
        l = self._tci_data_listeners[data_type]
        if callback in l:
            l.remove(callback)

    def _get_param_listeners(self, item):
        """Retrieves the list of all parameter callbacks to notify for a particular parameter."""
        res = []
        if item in self._tci_param_listeners:
            res += self._tci_param_listeners[item]
        if "*" in self._tci_param_listeners:
            res += self._tci_param_listeners["*"]
        return res

    def _get_data_listeners(self, item):
        """Retrieves the list of all data callbacks to notify for a particular data type."""
        res = []
        if item in self._tci_data_listeners:
            res += self._tci_data_listeners[item]
        if "*" in self._tci_data_listeners:
            res += self._tci_data_listeners["*"]
        return res

    def get_cached_param_value(self, cmd_info, rx = None, sub_rx = None):
        """Retrieves the most recently received value for a specific parameter."""
        if cmd_info.has_rx and (rx is None or type(rx) is not int or rx < 0):
            raise ValueError(f"Command {command} requires specifying applicable receiver number (positive integer)")
        if cmd_info.has_sub_rx and (sub_rx is None or type(sub_rx) is not int or sub_rx < 0):
            raise ValueError(f"Command {command} requires specifying applicable sub-receiver/channel number (positive integer)")

        if not cmd_info.has_rx:
            if cmd_info.name in self._tci_params["system"]:
                return self._tci_params["system"][cmd_info.name]

        if not cmd_info.has_sub_rx:
            if rx in self._tci_params["receivers"]:
                if cmd_info.name in self._tci_params["receivers"][rx]:
                    return self._tci_params["receivers"][rx][cmd_info.name]

        if rx in self._tci_params["receivers"]:
            if sub_rx in self._tci_params["receivers"][rx]["channels"]:
                if cmd_info.name in self._tci_params["receivers"][rx]["channels"][sub_rx]:
                    return self._tci_params["receivers"][rx]["channels"][sub_rx][cmd_info.name]

        return None

    def _callback_complete(self, task):
        """Raises exceptions that occured within a notification callback."""
        self._cb_tasks.discard(task)
        task.result()

    def _schedule_callback(self, callback, *callback_args):
        """Schedules a notification callback, ensuring that the status is checked when complete."""
        task = asyncio.create_task(callback(*callback_args))
        task.add_done_callback(lambda task: task.result())

    async def _listen_main(self, ws):
        """Coroutine that maintains parameter cache and schedules data/parameter callbacks."""
        while True:
            status = await ws.recv()
            if isinstance(status, bytes):
                packet = tci.TciDataPacket.from_buf(status)
                for callback in self._get_data_listeners(packet.data_type):
                    self._schedule_callback(callback, packet)
                continue

            parts = status.strip(";").split(":", 1)
            cmd_name = parts[0].upper()
            assert(cmd_name in tci.COMMANDS)

            cmd_info = tci.COMMANDS[cmd_name]
            expected_params = cmd_info.total_params()
            if expected_params != 0:
                assert(len(parts) == 2)

                cmd_params = [Listener._convert_type(v) for v in parts[1].split(",")]
                assert(expected_params == -1 or len(cmd_params) == expected_params)

                if not cmd_info.has_rx:
                    if len(cmd_params) == 1:
                        cmd_params = cmd_params[0]
                    self._tci_params["system"][cmd_info.name] = cmd_params
                    for callback in self._get_param_listeners(cmd_info.name):
                        self._schedule_callback(callback, cmd_info.name, None, None, cmd_params)
                    continue

                param_rx = cmd_params.pop(0)
                dest = self._tci_params["receivers"]
                if param_rx not in dest:
                    dest[param_rx] = {}
                dest = dest[param_rx]

                param_sub_rx = None
                if cmd_info.has_sub_rx:
                    param_sub_rx = cmd_params.pop(0)
                    if "channels" not in dest:
                        dest["channels"] = {}
                    if param_sub_rx not in dest["channels"]:
                        dest["channels"][param_sub_rx] = {}
                    dest = dest["channels"][param_sub_rx]

                if len(cmd_params) != 0:
                    if len(cmd_params) == 1:
                        cmd_params = cmd_params[0]
                    dest[cmd_info.name] = cmd_params
                else:
                    cmd_params = None

                for callback in self._get_param_listeners(cmd_info.name):
                    self._schedule_callback(callback, cmd_info.name, param_rx, param_sub_rx, cmd_params)
            else:
                if cmd_info.name == "READY":
                    self._ready_event.set()
                for callback in self._get_param_listeners(cmd_info.name):
                    self._schedule_callback(callback, cmd_info.name, None, None, None)

    async def _sender_main(self, ws):
        """Coroutine that sends commands and data packets to the server."""
        while True:
            msg = await self._tci_send.get()
            await ws.send(msg)

    async def _launch_tasks(self):
        """Coroutine that initiates connection and creates listener/sender tasks."""
        async with websockets.connect(self.uri) as ws:
            self._listen_task = asyncio.create_task(self._listen_main(ws))
            self._sender_task = asyncio.create_task(self._sender_main(ws))
            self._connected_event.set()
            done, pending = await asyncio.wait([self._listen_task, self._sender_task], return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()

    async def send(self, data):
        """Coroutine to enqueue data for sending, ensuring it reaches the queue."""
        await self._tci_send.put(data)

    async def start(self):
        """Coroutine called to start the connection and listener/sender tasks."""
        if self._listen_task is None:
            self._tci_send = asyncio.Queue()
            self._connected_event = asyncio.Event()
            self._ready_event = asyncio.Event()
            asyncio.create_task(self._launch_tasks())
            await self._connected_event.wait()

    async def ready(self):
        """Coroutine to verify initial synchronization is complete before continuing."""
        await self._ready_event.wait()

    async def wait(self):
        """Coroutine used to wait for connection completion."""
        await asyncio.gather(self._listen_task)
