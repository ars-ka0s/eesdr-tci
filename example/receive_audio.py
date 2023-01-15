# The output from this example should be piped to an audio utility or written to a file.  For example:
# (with sample_format_uint=false, sample_rate=8000) python receive_audio.py | ffplay -nodisp -ar 8000 -f f32le -ac 2 -
# (with sample_format_uint=true, sample_rate=24000) python receive_audio.py | direwolf

from eesdr_tci.Listener import Listener
from eesdr_tci.tci import TciEventType
import asyncio
import json
import sys
import array

async def audio_receiver(uri, sample_rate, uint_fmt):
	tci_listener = Listener(uri)
	await tci_listener.start()

	event_queue = tci_listener.events()
	params_dict = tci_listener.params()
	send_queue =  tci_listener.send_queue()
	data_queue =  tci_listener.data_packets()

	ready = False
	while not ready:
		evt = await event_queue.get()
		if evt.event_type == TciEventType.COMMAND:
			if evt.cmd_info.name == "READY":
				await send_queue.put(f"AUDIO_SAMPLERATE:{sample_rate};")
				await send_queue.put("AUDIO_START:0;")
				ready = True

	ready = False
	while not ready:
		evt = await event_queue.get()
		if evt.event_type == TciEventType.PARAM_CHANGED:
			if evt.cmd_info.name == "AUDIO_SAMPLERATE":
				assert(evt.get_value(params_dict) == sample_rate)
				ready = True

	while True:
		evt = await event_queue.get()
		if evt.event_type == TciEventType.DATA_RECEIVED:
			packet = await data_queue.get()
			data = packet.data
			if uint_fmt:
				data = array.array('h', [int(min(1,max(-1,x))*32767) for x in packet.data])
			sys.stdout.buffer.write(data.tobytes())

with open("example_config.json", mode="r") as cf:
	cfg = json.load(cf)
	try:
		uri = cfg["uri"]
	except:
		print("TCI Websocket URI must be specified in example_config.json.")
		exit(1)

	sample_rate = 8000
	if "sample_rate" in cfg:
		sample_rate = cfg["sample_rate"]

	uint_fmt = False
	if "sample_format_uint" in cfg:
		uint_fmt = cfg["sample_format_uint"]

asyncio.run(audio_receiver(uri, sample_rate, uint_fmt))
