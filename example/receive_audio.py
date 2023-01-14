# The output from this example should be piped to an audio utility or written to a file.  For example:
# python receive_audio.py | ffplay -nodisp -ar 8000 -f f32le -ac 2 -

from eesdr_tci.Listener import Listener
from eesdr_tci.tci import TciEventType
import asyncio
import json
import sys

async def printer(uri):
	tci_listener = Listener(uri)
	await tci_listener.start()

	event_queue = tci_listener.events()
	params_dict = tci_listener.params()
	send_queue =  tci_listener.send_queue()
	data_queue =  tci_listener.data_packets()

	while True:
		evt = await event_queue.get()
		if evt.event_type == TciEventType.COMMAND:
			if evt.cmd_info.name == "READY":
				await send_queue.put("AUDIO_SAMPLERATE:8000;")
				await send_queue.put("AUDIO_START:0;")
		elif evt.event_type == TciEventType.DATA_RECEIVED:
			packet = await data_queue.get()
			sys.stdout.buffer.write(packet.data.tobytes())

with open("example_config.json", mode="r") as cf:
	uri = json.load(cf)["uri"]

asyncio.run(printer(uri))
