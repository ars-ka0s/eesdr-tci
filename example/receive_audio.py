# The output from this example should be piped to an audio utility or written to a file.  For example:
# (with sample_format=0, sample_rate=8000)  python receive_audio.py | ffplay -nodisp -ar 8000  -f s16le -ac 2 -
# (with sample_format=3, sample_rate=48000) python receive_audio.py | ffplay -nodisp -ar 48000 -f f32le -ac 2 -

from eesdr_tci.Listener import Listener
from eesdr_tci.tci import TciEventType, TciSampleType
import asyncio
import json
import sys
import array

async def audio_receiver(uri, sample_rate, sample_fmt):
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
				await send_queue.put(f"AUDIO_STREAM_SAMPLE_TYPE:{sample_fmt.name.lower()};")
				ready = True

	ready = False
	while not ready:
		evt = await event_queue.get()
		if evt.event_type == TciEventType.PARAM_CHANGED:
			if evt.cmd_info.name == "AUDIO_SAMPLERATE":
				assert(evt.get_value(params_dict) == sample_rate)
			elif evt.cmd_info.name == "AUDIO_STREAM_SAMPLE_TYPE":
				assert(evt.get_value(params_dict) == sample_fmt.name.lower())
				ready = True

	await send_queue.put("AUDIO_START:0;")

	while True:
		evt = await event_queue.get()
		if evt.event_type == TciEventType.DATA_RECEIVED:
			packet = await data_queue.get()
			sys.stdout.buffer.write(packet.data)

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

sample_fmt = TciSampleType.INT16
if "sample_format" in cfg:
	sample_fmt = TciSampleType(cfg["sample_format"])

print(f"Connecting to {uri}", file=sys.stderr)
print(f"Using sample rate {sample_rate}, and sample_format {sample_fmt.name}.", file=sys.stderr)

asyncio.run(audio_receiver(uri, sample_rate, sample_fmt))
