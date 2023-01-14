from eesdr_tci.Listener import Listener
import asyncio
import json

async def printer(uri):
	tci_listener = Listener(uri)
	tci_listener.start()
	await asyncio.sleep(0)

	cmd_queue = tci_listener.cmds()
	params_dict = tci_listener.params()

	while True:
		cmd = await cmd_queue.get()
		if cmd[0] == "READY":
			print(json.dumps(params_dict))
			break

with open("example_config.json", mode="r") as cf:
	uri = json.load(cf)["uri"]

asyncio.run(printer(uri))
