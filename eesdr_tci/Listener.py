import asyncio
import websockets
from . import tci

class Listener:
	def __init__(self, uri):
		self.uri = uri

	_tci_params = {"system":{}, "receivers":{}}
	_tci_evts = None
	_tci_send = None
	_tci_data = None
	_listen_task = None
	_sender_task = None

	def _convert_type(val):
		try:
			return int(val)
		except:
			pass

		try:
			return float(val)
		except:
			pass

		if val.upper() == "TRUE":
			return True
		if val.upper() == "FALSE":
			return False

		return val

	async def _listen_main(self, ws):
		while True:
			status = await ws.recv()
			if type(status) is bytes:
				packet = tci.TciDataPacket.from_buf(status)
				await self._tci_data.put(packet)
				await self._tci_evts.put(tci.TciEvent(packet.data_type.name, tci.TciEventType.DATA_RECEIVED, packet.rx))
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
					await self._tci_evts.put(tci.TciEvent(cmd_info, tci.TciEventType.PARAM_CHANGED))
					continue

				param_rx = cmd_params.pop(0)
				dest = self._tci_params["receivers"]
				if param_rx not in dest:
					dest[param_rx] = {}
				dest = dest[param_rx]

				param_sub_rx = -1
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
					await self._tci_evts.put(tci.TciEvent(cmd_info, tci.TciEventType.PARAM_CHANGED, param_rx, param_sub_rx))
				else:
					await self._tci_evts.put(tci.TciEvent(cmd_info, tci.TciEventType.COMMAND, param_rx, param_sub_rx))
			else:
				await self._tci_evts.put(tci.TciEvent(cmd_info, tci.TciEventType.COMMAND))

	async def _sender_main(self, ws):
		while True:
			msg = await self._tci_send.get()
			await ws.send(msg)

	async def _launch_tasks(self):
		async with websockets.connect(self.uri) as ws:
			self._listen_task = asyncio.create_task(self._listen_main(ws))
			self._sender_task = asyncio.create_task(self._sender_main(ws))
			done, pending = await asyncio.wait([self._listen_task, self._sender_task], return_when=asyncio.FIRST_COMPLETED)
			for task in pending:
				task.cancel()

	def params(self):
		return self._tci_params

	def events(self):
		return self._tci_evts

	def data_packets(self):
		return self._tci_data

	def send_queue(self):
		return self._tci_send

	async def start(self):
		if self._listen_task is None:
			self._tci_evts = asyncio.Queue()
			self._tci_send = asyncio.Queue()
			self._tci_data = asyncio.Queue()
			asyncio.create_task(self._launch_tasks())
			await asyncio.sleep(0)
