"""The listener module contains the main Listener class which interacts with the TCI server."""

import asyncio
from asyncio.exceptions import CancelledError
import websockets

from . import tci

class Listener:
    """The Listener class interacts with the TCI server by listening for parameter updates.
    A sender task also passes formatted command strings & data packets to the server.
    Parameter and data stream callbacks can be registered to be notified of changes of interest,
    as many commands may be ignorable in certain use cases.
    """

    def __init__(self, uri):
        self.uri = uri
        self._tci_param_listeners = {}
        self._tci_data_listeners = {}
        self._tci_send = None
        self._launch_task = None
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

    def _schedule_callback(self, callback, *callback_args):
        """Schedules a notification callback, ensuring that the status is checked when complete."""
        task = asyncio.create_task(callback(*callback_args))
        task.add_done_callback(lambda task: task.result())

    async def _listen_main(self, ws):
        """Coroutine that receives from the server and schedules data/parameter callbacks."""
        while True:
            status = await ws.recv()

            if isinstance(status, bytes):
                packet = tci.TciDataPacket.from_buf(status)
                for callback in self._get_data_listeners(packet.data_type):
                    self._schedule_callback(callback, packet)
                continue

            parts = status.strip(";").split(":", 1)
            cmd_name = parts[0].upper()
            if cmd_name not in tci.COMMANDS:
                raise ValueError(f'Command {cmd_name} unrecognized')

            cmd_info = tci.COMMANDS[cmd_name]
            expected_params = cmd_info.total_params()

            if expected_params == 0:
                if cmd_info.name == "READY":
                    self._ready_event.set()
                for callback in self._get_param_listeners(cmd_info.name):
                    self._schedule_callback(callback, cmd_info.name, None, None, None)
                continue

            if len(parts) != 2:
                raise ValueError(f'Command {cmd_name} should have parameters, but none received.')

            cmd_params = [Listener._convert_type(v) for v in parts[1].split(",")]
            param_cnt = len(cmd_params)
            if expected_params not in (-1, param_cnt):
                raise ValueError(f'Command {cmd_name} should have {expected_params} params, received {param_cnt}')

            param_rx = None
            if cmd_info.has_rx:
                param_rx = cmd_params.pop(0)
                param_cnt -= 1

            param_sub_rx = None
            if cmd_info.has_sub_rx:
                param_sub_rx = cmd_params.pop(0)
                param_cnt -= 1

            if param_cnt == 1:
                cmd_params = cmd_params[0]
            elif param_cnt == 0:
                cmd_params = None

            for callback in self._get_param_listeners(cmd_info.name):
                self._schedule_callback(callback, cmd_info.name, param_rx, param_sub_rx, cmd_params)

    async def _sender_main(self, ws):
        """Coroutine that sends commands and data packets to the server."""
        while True:
            msg = await self._tci_send.get()
            await ws.send(msg)

    async def _launch_tasks(self):
        """Coroutine that initiates connection and creates listener/sender tasks."""
        try:
            async with websockets.connect(self.uri) as ws:
                listen_task = asyncio.create_task(self._listen_main(ws))
                sender_task = asyncio.create_task(self._sender_main(ws))
                self._connected_event.set()
                try:
                    await listen_task
                    await sender_task
                except CancelledError:
                    listen_task.cancel()
                    sender_task.cancel()
        except CancelledError:
            pass

    async def send(self, data):
        """Coroutine to enqueue data for sending, ensuring it reaches the queue."""
        await self._tci_send.put(data)

    def send_nowait(self, data):
        """Enqueue data for sending without ensuring it reaches the queue."""
        self._tci_send.put_nowait(data)

    async def start(self, timeout=3.0):
        """Coroutine called to start the connection and listener/sender tasks."""
        if self._launch_task is not None and not self._launch_task.done():
            return
        self._tci_send = asyncio.Queue()
        self._connected_event = asyncio.Event()
        self._ready_event = asyncio.Event()
        self._launch_task = asyncio.create_task(self._launch_tasks())
        async def _await_conn():
            await self._connected_event.wait()
        done, _ = await asyncio.wait([asyncio.create_task(_await_conn())], timeout=timeout)
        if len(done) == 0:
            self._launch_task.cancel()
            try:
                await self._launch_task
            except CancelledError:
                pass
            except Exception as exc:
                raise TimeoutError(f'Connected event not received after {timeout} sec.') from exc
            raise TimeoutError(f'Connected event not received after {timeout} sec.')

    def shutdown(self):
        """Cancels communication tasks and shut down connection."""
        self._launch_task.cancel()

    async def ready(self, timeout=3.0):
        """Coroutine to verify initial synchronization is complete before continuing."""
        async def _await_ready():
            await self._ready_event.wait()
        done, _ = await asyncio.wait([asyncio.create_task(_await_ready())], timeout=timeout)
        if len(done) == 0:
            self._launch_task.cancel()
            try:
                await self._launch_task
            except CancelledError:
                pass
            except Exception as exc:
                raise TimeoutError(f'Ready event not received after {timeout} sec.') from exc
            raise TimeoutError(f'Ready event not received after {timeout} sec.')

    async def wait(self):
        """Coroutine used to wait for connection completion."""
        await self._launch_task
