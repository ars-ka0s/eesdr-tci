import asyncio
import websockets
from . import tci

class Listener:
	def __init__(self, uri):
		self.uri = uri

	_tci_params = {}
	_tci_cmds = None
	_listen_task = None

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
				cmd_params = parts[1].split(",")
				assert(expected_params == -1 or len(cmd_params) == expected_params)
				val_idx = 0
				if cmd_info.has_rx:
					param_rx = cmd_params[0]
					val_idx = 1
				else:
					param_rx = -1
				if cmd_info.has_sub_rx:
					param_sub_rx = cmd_params[1]
					val_idx = 2
				else:
					param_sub_rx = -1
				if param_rx not in self._tci_params:
					self._tci_params[param_rx] = {}
				if param_sub_rx not in self._tci_params[param_rx]:
					self._tci_params[param_rx][param_sub_rx] = {}
				self._tci_params[param_rx][param_sub_rx][cmd_info.name] = cmd_params[val_idx:]
				await self._tci_cmds.put((cmd_info.name, param_rx, param_sub_rx))
			else:
				await self._tci_cmds.put((cmd_info.name, -1, -1))
	
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
