from eesdr_tci import tci
from eesdr_tci.listener import Listener
from eesdr_tci.tci import TciCommandSendAction
from config import Config
import json
import asyncio
import functools
from datetime import datetime

stations = None

squelch_level = 0
if_limits = []
rx_dds = 0
filter_band = []

async def update_params(name, rx, subrx, params):
    global squelch_level, if_limits, rx_dds, filter_band

    if rx is not None and rx != 0:
        return

    if name == "SQL_LEVEL":
        squelch_level = params
    elif name == "IF_LIMITS":
        if_limits = params
    elif name == "DDS":
        rx_dds = params
    elif name == "RX_FILTER_BAND":
        filter_band = params

async def next_frequency(tci_listener, next_station_event, monitor_station_event):
    global if_limits, rx_dds, filter_band
    global stations

    stations_idx = 0

    while True:
        await next_station_event.wait()

        station = stations[stations_idx]
        stations_idx += 1
        if stations_idx >= len(stations):
            stations_idx = 0
        
        sta_freq = station["freq"]
        sta_dds = rx_dds
        sta_if = sta_freq - sta_dds
        edge_offsets = [5000 - filter_band[0], 5000 + filter_band[1]]

        if sta_if - edge_offsets[0] < if_limits[0] or sta_if + edge_offsets[1] > if_limits[1]:
            sta_if = if_limits[0] + edge_offsets[0]
            sta_dds = sta_freq - sta_if
        
        print(f"{str(datetime.now()).ljust(30)} Tuning to {sta_freq}")

        await tci_listener.send(tci.COMMANDS["DDS"].prepare_string(TciCommandSendAction.WRITE, rx=0, params=[int(sta_dds)]))
        await tci_listener.send(tci.COMMANDS["IF"].prepare_string(TciCommandSendAction.WRITE, rx=0, sub_rx=0, params=[int(sta_if)]))

        next_station_event.clear()
        monitor_station_event.set()

async def rx_sensors(readings_queue, name, rx, subrx, params):
    if rx != 0:
        return

    await readings_queue.put(params)

async def monitor_station(tci_listener, next_station_event, monitor_station_event, wait_time=1.0, hold_time=3.0):
    global squelch_level

    while True:
        await monitor_station_event.wait()
        readings_queue = asyncio.Queue()
        partial = functools.partial(rx_sensors, readings_queue)
        tci_listener.add_param_listener("RX_SENSORS", partial)

        hold = False
        for i in range(int(wait_time/0.2)):
            reading = await readings_queue.get()
            if reading > squelch_level:
                hold = True
                break
        
        if hold:
            print(f"{str(datetime.now()).ljust(30)} Activity detected")
            i = 0
            while i < int(hold_time/0.2):
                reading = await readings_queue.get()
                if reading > squelch_level:
                    i = 0
                else:
                    i += 1

        print(f"{str(datetime.now()).ljust(30)} No activity detected")        
        tci_listener.remove_param_listener("RX_SENSORS", partial)
        
        monitor_station_event.clear()
        next_station_event.set()

async def main(uri, wait_time, hold_time):
    next_station_event = asyncio.Event()
    monitor_station_event = asyncio.Event()
    readings_queue = asyncio.Queue()

    tci_listener = Listener(uri)

    tci_listener.add_param_listener("SQL_LEVEL", update_params)
    tci_listener.add_param_listener("IF_LIMITS", update_params)
    tci_listener.add_param_listener("DDS", update_params)
    tci_listener.add_param_listener("RX_FILTER_BAND", update_params)

    await tci_listener.start()
    await tci_listener.ready()

    await tci_listener.send(tci.COMMANDS["RX_SENSORS_ENABLE"].prepare_string(TciCommandSendAction.WRITE, params=[True, 200]))

    asyncio.create_task(next_frequency(tci_listener, next_station_event, monitor_station_event))
    asyncio.create_task(monitor_station(tci_listener, next_station_event, monitor_station_event, wait_time, hold_time))

    next_station_event.set()

    await tci_listener.wait()

cfg = Config("example_config.json")
uri = cfg.get("uri", required=True)
scanner_file_name = cfg.get("scanner_file", required=True)
wait_time = cfg.get("scanner_wait_time", default=1.0)
hold_time = cfg.get("scanner_hold_time", default=3.0)

with open(scanner_file_name, mode="r") as scanner_file:
    scanner_json = json.load(scanner_file)

stations = [v for k,v in scanner_json.items()]
stations.sort(key=lambda s: s["freq"])

asyncio.run(main(uri, wait_time, hold_time))
