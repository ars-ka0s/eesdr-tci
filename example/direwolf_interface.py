from eesdr_tci.Listener import Listener
from eesdr_tci.tci import TciEventType, TciStreamType, TciSampleType, TciDataPacket
import asyncio
import json
import sys
import array

SAMPLE_BUFSIZE = 2048

async def data_printer(stream):
	async for d in stream:
		print(d.decode('utf-8'), end='')

async def transmit_receiver(stream, event, queue):
	while True:
		dat = await stream.read(2*SAMPLE_BUFSIZE)
		await queue.put(array.array("h", dat))
		event.set()

async def transmit_sender(send_queue, tx_data_received, tx_data_queue, tx_chrono_queue):
	tx_buf = array.array('h')
	while True:
		await tx_data_received.wait()
		await send_queue.put("TRX:0,true,tci")
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
			await send_queue.put(packet.to_bytes())
			await asyncio.sleep(0)
			if buf_avail < SAMPLE_BUFSIZE:
				break
		await send_queue.put("TRX:0,false")
		while tx_chrono_queue.qsize() > 0:
			await tx_chrono_queue.get()
		tx_data_received.clear()

async def audio_receiver(uri, sample_rate):
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
				await send_queue.put(f"AUDIO_STREAM_CHANNELS:1;")
				await send_queue.put(f"AUDIO_STREAM_SAMPLE_TYPE:int16;")
				await send_queue.put(f"AUDIO_STREAM_SAMPLES:{SAMPLE_BUFSIZE};")
				ready = True

	ready = False
	while not ready:
		evt = await event_queue.get()
		if evt.event_type == TciEventType.PARAM_CHANGED:
			if evt.cmd_info.name == "AUDIO_SAMPLERATE":
				assert(evt.get_value(params_dict) == sample_rate)
			elif evt.cmd_info.name == "AUDIO_STREAM_CHANNELS":
				assert(evt.get_value(params_dict) == 1)
			elif evt.cmd_info.name == "AUDIO_STREAM_SAMPLE_TYPE":
				assert(evt.get_value(params_dict) == "int16")
			elif evt.cmd_info.name == "AUDIO_STREAM_SAMPLES":
				assert(evt.get_value(params_dict) == SAMPLE_BUFSIZE)
				ready = True

	dw_proc = await asyncio.create_subprocess_exec("./direwolf-stdout", "-O", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
	printer_task = asyncio.create_task(data_printer(dw_proc.stderr))
	tx_data_queue = asyncio.Queue()
	tx_data_received = asyncio.Event()
	transmit_listen_task = asyncio.create_task(transmit_receiver(dw_proc.stdout, tx_data_received, tx_data_queue))
	tx_chrono_queue = asyncio.Queue()
	transmit_sender_task = asyncio.create_task(transmit_sender(send_queue, tx_data_received, tx_data_queue, tx_chrono_queue))
	await asyncio.sleep(0)

	await send_queue.put("AUDIO_START:0;")

	while True:
		evt = await event_queue.get()
		if evt.event_type != TciEventType.DATA_RECEIVED:
			if evt.cmd_info.name == "TRX":
				print("PTT", "On" if evt.get_value(params_dict) else "Off")
			continue
		if evt.cmd_info == "RX_AUDIO_STREAM":
			packet = await data_queue.get()
			data = array.array('h', packet.data)
			dw_proc.stdin.write(data.tobytes())
			await dw_proc.stdin.drain()
		if evt.cmd_info == "TX_CHRONO":
			packet = await data_queue.get()
			await tx_chrono_queue.put(0)

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

print(f"Connecting to {uri} and using sample_rate of {sample_rate} on 1 channel. Make sure this matches direwolf below (set using ARATE/ACHANNELS in direwolf.conf).")
asyncio.run(audio_receiver(uri, sample_rate))
