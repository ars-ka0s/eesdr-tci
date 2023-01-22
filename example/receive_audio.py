# The output from this example should be piped to an audio utility or written to a file.  For example:
# (with sample_format=0, sample_rate=8000)  python receive_audio.py | ffplay -nodisp -ar 8000  -f s16le -ac 2 -
# (with sample_format=3, sample_rate=48000) python receive_audio.py | ffplay -nodisp -ar 48000 -f f32le -ac 2 -

from eesdr_tci import tci
from eesdr_tci.Listener import Listener
from eesdr_tci.tci import TciSampleType, TciCommandSendAction, TciStreamType
from config import Config
import asyncio
import sys
import array

tci_listener = None
sr_verified = None
sst_verified = None

async def verify_response(command, rx, subrx, param):
	if command == "AUDIO_SAMPLERATE":
		assert(param == sample_rate)
		sr_verified.set()
	elif command == "AUDIO_STREAM_SAMPLE_TYPE":
		assert(param == sample_fmt.name.lower())
		sst_verified.set()

async def receive_data(packet):
	sys.stdout.buffer.write(packet.data)

async def audio_receiver(uri, sample_rate, sample_fmt):
	global tci_listener, sr_verified, sst_verified

	tci_listener = Listener(uri)
	sr_verified = asyncio.Event()
	sst_verified = asyncio.Event()

	await tci_listener.start()
	await tci_listener.ready()

	tci_listener.add_param_listener("AUDIO_SAMPLERATE", verify_response)
	tci_listener.add_param_listener("AUDIO_STREAM_SAMPLE_TYPE", verify_response)

	await tci_listener.send(tci.COMMANDS["AUDIO_SAMPLERATE"].prepare_string(TciCommandSendAction.WRITE, params=[sample_rate]))
	await tci_listener.send(tci.COMMANDS["AUDIO_STREAM_SAMPLE_TYPE"].prepare_string(TciCommandSendAction.WRITE, params=[sample_fmt.name.lower()]))

	await sr_verified.wait()
	await sst_verified.wait()

	tci_listener.add_data_listener(TciStreamType.RX_AUDIO_STREAM, receive_data)

	await tci_listener.send(tci.COMMANDS["AUDIO_START"].prepare_string(TciCommandSendAction.WRITE, rx=0))

	await tci_listener.wait()

cfg = Config("example_config.json")
uri = cfg.get("uri", required=True)
sample_rate = cfg.get("sample_rate", default=8000)
sample_fmt = TciSampleType(cfg.get("sample_format", default=TciSampleType.INT16.value))

print(f"Connecting to {uri}", file=sys.stderr)
print(f"Using sample rate {sample_rate}, and sample_format {sample_fmt.name}.", file=sys.stderr)

asyncio.run(audio_receiver(uri, sample_rate, sample_fmt))
