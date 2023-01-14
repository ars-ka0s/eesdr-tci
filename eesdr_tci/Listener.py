import asyncio
import websockets
from . import tci

class Listener:
	def __init__(self, uri):
		self.uri = uri

	_tci_params = {"system":{}, "receivers":{}}
	_tci_cmds = None
	_listen_task = None

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

	async def _tci_status_rx(self, ws):
		while True:
			status = await ws.recv()
			parts = status.strip(";").split(":", 1)
			cmd_name = parts[0].upper()
			assert(cmd_name in tci._COMMANDS)

			cmd_info = tci._COMMANDS[cmd_name]
			expected_params = cmd_info.total_params()
			if expected_params != 0:
				assert(len(parts) == 2)

				cmd_params = [Listener._convert_type(v) for v in parts[1].split(",")]
				assert(expected_params == -1 or len(cmd_params) == expected_params)

				if not cmd_info.has_rx:
					if len(cmd_params) == 1:
						cmd_params = cmd_params[0]
					self._tci_params["system"][cmd_info.name] = cmd_params
					await self._tci_cmds.put((cmd_info.name, "system"))
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

				if len(cmd_params) == 1:
					cmd_params = cmd_params[0]
				dest[cmd_info.name] = cmd_params
				await self._tci_cmds.put((cmd_info.name, "receivers", param_rx, param_sub_rx))
			else:
				await self._tci_cmds.put((cmd_info.name, "command"))

	async def _listen_main(self):
		self._tci_cmds = asyncio.Queue()
		async with websockets.connect(self.uri) as ws:
			await self._tci_status_rx(ws)

	def params(self):
		return self._tci_params

	def cmds(self):
		return self._tci_cmds

	def start(self):
		if self._listen_task is None:
			self._listen_task = asyncio.create_task(self._listen_main())
