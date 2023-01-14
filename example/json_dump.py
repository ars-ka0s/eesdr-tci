from eesdr_tci.Listener import Listener
import asyncio
import json

async def printer(uri):
	tci_listener = Listener(uri)
	await tci_listener.start()

	event_queue = tci_listener.events()
	params_dict = tci_listener.params()

	while True:
		evt = await event_queue.get()
		if evt.cmd_info.name == "READY":
			print(json.dumps(params_dict))
			break

with open("example_config.json", mode="r") as cf:
	uri = json.load(cf)["uri"]

asyncio.run(printer(uri))
