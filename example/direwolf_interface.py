from eesdr_tci import tci
from eesdr_tci.Listener import Listener
from eesdr_tci.tci import TciStreamType, TciSampleType, TciDataPacket, TciCommandSendAction
from config import Config
import asyncio
import sys
import array
import functools

SAMPLE_BUFSIZE = 2048

async def data_printer(stderr_stream):
	async for d in stderr_stream:
		print(d.decode('utf-8'), end='')

async def transmit_receiver(stdout_stream, tx_data_received, tx_data_queue):
	while True:
		dat = await stdout_stream.read(2*SAMPLE_BUFSIZE)
		await tx_data_queue.put(array.array("h", dat))
		tx_data_received.set()

async def transmit_sender(tx_data_received, tx_data_queue, tx_chrono_queue):
	tx_buf = array.array('h')
	while True:
		await tx_data_received.wait()
		await tci_listener.send(tci.COMMANDS["TRX"].prepare_string(TciCommandSendAction.WRITE, rx=0, params=["true", "tci"], check_params=False))
		while True:
			try:
				await asyncio.wait_for(tx_chrono_queue.get(), timeout = 3.0)
			except asyncio.exceptions.TimeoutError:
				print("Unexpected no chrono packet")
				break
			packet = TciDataPacket(0, 24000, TciSampleType.INT16, 0, 0, SAMPLE_BUFSIZE, TciStreamType.TX_AUDIO_STREAM, 1, None)
			buf_avail = SAMPLE_BUFSIZE
			while len(tx_buf) < SAMPLE_BUFSIZE:
				try:
					dat = await asyncio.wait_for(tx_data_queue.get(), timeout=0.1)
					tx_buf += dat
				except asyncio.exceptions.TimeoutError:
					buf_avail = len(tx_buf)
					break
			packet.length = buf_avail
			packet.data = tx_buf[0:buf_avail].tobytes()
			if len(tx_buf) > buf_avail:
				tx_buf = tx_buf[buf_avail:]
			else:
				tx_buf = array.array('h')
			await tci_listener.send(packet.to_bytes())
			await asyncio.sleep(0)
			if buf_avail < SAMPLE_BUFSIZE:
				break
		await tci_listener.send(tci.COMMANDS["TRX"].prepare_string(TciCommandSendAction.WRITE, rx=0, params=["false"]))
		while tx_chrono_queue.qsize() > 0:
			await tx_chrono_queue.get()
		tx_data_received.clear()

tci_listener = None
rate_verified = None
chans_verified = None
type_verified = None
samples_verified = None

async def verify_response(name, rx, subrx, params):
	if name == "AUDIO_SAMPLERATE":
		assert(params == sample_rate)
		rate_verified.set()
		tci_listener.remove_param_listener(name, verify_response)
	elif name == "AUDIO_STREAM_CHANNELS":
		assert(params == 1)
		chans_verified.set()
		tci_listener.remove_param_listener(name, verify_response)
	elif name == "AUDIO_STREAM_SAMPLE_TYPE":
		assert(params == "int16")
		type_verified.set()
		tci_listener.remove_param_listener(name, verify_response)
	elif name == "AUDIO_STREAM_SAMPLES":
		assert(params == SAMPLE_BUFSIZE)
		samples_verified.set()
		tci_listener.remove_param_listener(name, verify_response)

async def show_ptt(name, rx, subrx, params):
	print(f"PTT {rx} {'On' if params else 'Off'}")

async def handle_rx_audio(stdin_stream, packet):
	data = array.array('h', packet.data)
	stdin_stream.write(data.tobytes())
	await stdin_stream.drain()

async def audio_receiver(uri, sample_rate):
	global tci_listener, rate_verified, chans_verified, type_verified, samples_verified

	tci_listener = Listener(uri)
	await tci_listener.start()
	await tci_listener.ready()

	rate_verified = asyncio.Event()
	chans_verified = asyncio.Event()
	type_verified = asyncio.Event()
	samples_verified = asyncio.Event()

	tci_listener.add_param_listener("AUDIO_SAMPLERATE", verify_response)
	tci_listener.add_param_listener("AUDIO_STREAM_CHANNELS", verify_response)
	tci_listener.add_param_listener("AUDIO_STREAM_SAMPLE_TYPE", verify_response)
	tci_listener.add_param_listener("AUDIO_STREAM_SAMPLES", verify_response)

	await tci_listener.send(tci.COMMANDS["AUDIO_SAMPLERATE"].prepare_string(TciCommandSendAction.WRITE, params=[sample_rate]))
	await tci_listener.send(tci.COMMANDS["AUDIO_STREAM_CHANNELS"].prepare_string(TciCommandSendAction.WRITE, params=[1]))
	await tci_listener.send(tci.COMMANDS["AUDIO_STREAM_SAMPLE_TYPE"].prepare_string(TciCommandSendAction.WRITE, params=["int16"]))
	await tci_listener.send(tci.COMMANDS["AUDIO_STREAM_SAMPLES"].prepare_string(TciCommandSendAction.WRITE, params=[SAMPLE_BUFSIZE]))

	await rate_verified.wait()
	await chans_verified.wait()
	await type_verified.wait()
	await samples_verified.wait()

	dw_proc = await asyncio.create_subprocess_exec("./direwolf-stdout", "-O", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
	printer_task = asyncio.create_task(data_printer(dw_proc.stderr))
	tx_data_queue = asyncio.Queue()
	tx_data_received = asyncio.Event()
	transmit_listen_task = asyncio.create_task(transmit_receiver(dw_proc.stdout, tx_data_received, tx_data_queue))
	tx_chrono_queue = asyncio.Queue()
	transmit_sender_task = asyncio.create_task(transmit_sender(tx_data_received, tx_data_queue, tx_chrono_queue))
	await asyncio.sleep(0)

	tci_listener.add_param_listener("TRX", show_ptt)
	tci_listener.add_data_listener(TciStreamType.TX_CHRONO, tx_chrono_queue.put)
	tci_listener.add_data_listener(TciStreamType.RX_AUDIO_STREAM, functools.partial(handle_rx_audio, dw_proc.stdin))

	await tci_listener.send(tci.COMMANDS["AUDIO_START"].prepare_string(TciCommandSendAction.WRITE, rx=0))

	await tci_listener.wait()

cfg = Config("example_config.json")
uri = cfg.get("uri", required=True)
sample_rate = cfg.get("sample_rate", default=8000)

print(f"Connecting to {uri} and using sample_rate of {sample_rate} on 1 channel. Make sure this matches direwolf below (set using ARATE/ACHANNELS in direwolf.conf).")
asyncio.run(audio_receiver(uri, sample_rate))
