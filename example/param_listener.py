from eesdr_tci.Listener import Listener
from config import Config
import asyncio

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

cfg = Config("example_config.json")
uri = cfg.get("uri", required=True)

asyncio.run(printer(uri))
