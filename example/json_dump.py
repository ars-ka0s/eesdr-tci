from eesdr_tci.Listener import Listener
import asyncio
import json

params_dict = {"system":{},"receivers":{}}

async def update_params(name, rx, subrx, params):
	if params is None:
		return
	
	if rx is None:
		params_dict["system"][name] = params
		return
	
	if rx not in params_dict["receivers"]:
		params_dict["receivers"][rx] = {"channels":{}}

	if subrx is None:
		params_dict["receivers"][rx][name] = params
		return
	
	if subrx not in params_dict["receivers"][rx]["channels"]:
		params_dict["receivers"][rx]["channels"][subrx] = {}
	
	params_dict["receivers"][rx]["channels"][subrx][name] = params

async def printer(uri):
	tci_listener = Listener(uri)
	tci_listener.add_param_listener("*", update_params)
	await tci_listener.start()
	await tci_listener.ready()
	print(json.dumps(params_dict))

with open("example_config.json", mode="r") as cf:
	uri = json.load(cf)["uri"]

asyncio.run(printer(uri))
