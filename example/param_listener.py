from eesdr_tci.Listener import Listener
import asyncio
import json

ready = False
squelch = 0

async def print_params(name, rx, subrx, params):
	print(f'{name.ljust(40)} {" " if rx is None else rx} {" " if subrx is None else subrx}   {params}')
	if name == "READY":
		ready = True

async def printer(uri):
	tci_listener = Listener(uri)

	tci_listener.add_param_listener("*", print_params)

	await tci_listener.start()
	await tci_listener.ready()
	await tci_listener.wait()

with open("example_config.json", mode="r") as cf:
	uri = json.load(cf)["uri"]

asyncio.run(printer(uri))
