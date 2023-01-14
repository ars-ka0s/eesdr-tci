from eesdr_tci.Listener import Listener
from eesdr_tci.tci import TciEventType
import asyncio
import json

async def printer(uri):
	tci_listener = Listener(uri)
	tci_listener.start()
	await asyncio.sleep(0)

	event_queue = tci_listener.events()
	params_dict = tci_listener.params()

	while True:
		evt = await event_queue.get()
		if evt.event_type == TciEventType.COMMAND:
			print(evt)
		else:
			print(str(evt).ljust(60), evt.get_value(params_dict))

with open("example_config.json", mode="r") as cf:
	uri = json.load(cf)["uri"]

asyncio.run(printer(uri))
