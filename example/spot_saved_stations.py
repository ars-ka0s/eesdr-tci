# This utility reads an SBJ file exported from the EESDR station list (or handcrafted)
# and spots the stations it contains.  It can optionally continually respot the stations
# so the names never fall off the display.

from eesdr_tci.Listener import Listener
from eesdr_tci import tci
from eesdr_tci.tci import TciCommandSendAction
import json
import asyncio
from datetime import datetime

def get_cfg(cfg, prop, default=None, required=False):
	res = default
	try:
		res = cfg[prop]
	except:
		if required:
			print(f"{prop} must be specified in configuration file.")
			exit(1)
	return res

async def main(uri, spot_params, respot_time):
	tci_listener = Listener(uri)
	await tci_listener.start()
	await tci_listener.ready()

	ready = True
	while ready:
		print(datetime.now().ctime())
		for p in spot_params:
			await tci_listener.send(tci.COMMANDS["SPOT"].prepare_string(TciCommandSendAction.WRITE, params=p))
		print(f"Spotting {p[0]}")

		if respot_time:
			await asyncio.sleep(respot_time)
		else:
			ready = False

with open("example_config.json", mode="r") as cf:
	cfg = json.load(cf)

uri = get_cfg(cfg, "uri", required=True)
saved_stations_file = get_cfg(cfg, "saved_stations_file", required=True)
respot_time = get_cfg(cfg, "respot_time", default=60)
spot_color = get_cfg(cfg, "spot_color", default="#aa2222")

color_val = int("0xFF" + spot_color.lstrip("#"), 16)

with open(saved_stations_file, mode="r") as f:
	stations_json = f.read()
stations = json.loads(stations_json)

spot_params = [[s["comment"], s["modulation"], s["freq"], color_val, s["comment"]] for s in stations.values()]

asyncio.run(main(uri, spot_params, respot_time))
