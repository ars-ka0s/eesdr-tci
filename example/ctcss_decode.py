from eesdr_tci import tci
from eesdr_tci.listener import Listener
from eesdr_tci.tci import TciCommandSendAction, TciStreamType
from config import Config
from scipy.signal import ZoomFFT
import asyncio
import sys
import array
import functools

class CTCSS:
    # These are the somewhat standard number order, sourced from the Wikipedia article on CTCSS
    # https://en.wikipedia.org/wiki/Continuous_Tone-Coded_Squelch_System#List_of_tones when accessed 23 Jan 2023
    FREQS = [150.0, 67, 71.9, 74.4, 77, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8, 97.4, 100, 103.5, 107.2, 110.9, 114.8, 118.8, 123, 127.3, 131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 162.2, 167.9, 173.8, 179.9, 186.2, 192.8, 203.5, 210.7, 218.1, 225.7, 233.6, 241.8, 250.3, 69.3, 159.8, 165.5, 171.3, 177.3, 183.5, 189.9, 196.6, 199.5, 206.5, 229.1, 254.1]
    FREQS_IDX = [int(f * 10) for f in FREQS]

    def __init__(self, sample_size, max_freq, freq_res, sample_rate, process_rate):
        self._sample_size = sample_size
        self._process_buff_extra = sample_rate / process_rate
        self._zfft = ZoomFFT(n = sample_size, fn = max_freq, m = int(max_freq / freq_res) + 1, fs = sample_rate, endpoint = True)
        self._buff = array.array('h')

    def process(self, raw_data):
        self._buff += array.array('h', raw_data)
        if len(self._buff) < self._sample_size + self._process_buff_extra:
            return None
        self._buff = self._buff[-self._sample_size:]
        fft = self._zfft(self._buff)
        mag = [abs(fft[i]) for i in CTCSS.FREQS_IDX]
        mean_mag = sum(mag) / len(mag)

        if mean_mag > 1:
            norm_mag = [m / mean_mag for m in mag]
            peak_mag = [(f, m) for (f, m) in zip(CTCSS.FREQS, norm_mag) if m > 10]
            peak_mag.sort(key = lambda v: v[1], reverse = True)
            return peak_mag

        return None

tci_listener = None
sr_verified = None
sch_verified = None
sst_verified = None

async def verify_response(command, rx, subrx, param):
    if command == "AUDIO_SAMPLERATE":
        assert(param == sample_rate)
        sr_verified.set()
    elif command == "AUDIO_STREAM_CHANNELS":
        assert(param == 1)
        sch_verified.set()
    elif command == "AUDIO_STREAM_SAMPLE_TYPE":
        assert(param == "int16")
        sst_verified.set()

async def receive_data(ctcss, packet):
    peaks = ctcss.process(packet.data)

    if peaks is None:
        return
    for (f, m) in peaks:
        i = CTCSS.FREQS.index(f)
        if m > 20:
            conf_desc = "(high)"
        else:
            conf_desc = "(low)"
        print(f"PL {f:.1f} Hz [idx {i}] (Conf {m:.2f} {conf_desc})")

async def audio_receiver(uri, sample_rate, ctcss_process_rate):
    global tci_listener, sr_verified, sch_verified, sst_verified

    tci_listener = Listener(uri)
    sr_verified = asyncio.Event()
    sch_verified = asyncio.Event()
    sst_verified = asyncio.Event()

    await tci_listener.start()
    await tci_listener.ready()

    tci_listener.add_param_listener("AUDIO_SAMPLERATE", verify_response)
    tci_listener.add_param_listener("AUDIO_STREAM_CHANNELS", verify_response)
    tci_listener.add_param_listener("AUDIO_STREAM_SAMPLE_TYPE", verify_response)

    await tci_listener.send(tci.COMMANDS["AUDIO_SAMPLERATE"].prepare_string(TciCommandSendAction.WRITE, params=[sample_rate]))
    await tci_listener.send(tci.COMMANDS["AUDIO_STREAM_CHANNELS"].prepare_string(TciCommandSendAction.WRITE, params=[1]))
    await tci_listener.send(tci.COMMANDS["AUDIO_STREAM_SAMPLE_TYPE"].prepare_string(TciCommandSendAction.WRITE, params=["int16"]))

    await sr_verified.wait()
    await sst_verified.wait()

    ctcss = CTCSS(sample_rate, 300, 0.1, sample_rate, ctcss_process_rate)
    tci_listener.add_data_listener(TciStreamType.RX_AUDIO_STREAM, functools.partial(receive_data, ctcss))

    await tci_listener.send(tci.COMMANDS["AUDIO_START"].prepare_string(TciCommandSendAction.WRITE, rx=0))

    await tci_listener.wait()

cfg = Config("example_config.json")
uri = cfg.get("uri", required=True)
sample_rate = cfg.get("sample_rate", default=8000)
ctcss_process_rate = cfg.get("ctcss_process_rate", default=3)

print(f"Connecting to {uri}")
print(f"Using sample rate {sample_rate} and processing {ctcss_process_rate} times per second.")

asyncio.run(audio_receiver(uri, sample_rate, ctcss_process_rate))
