from enum import Enum
import struct
import array

class _TciCommand:
	def __init__(self, name, readable = True, writeable = True, has_rx = False, has_sub_rx = False, param_count = 1):
		self.name = name
		self.readable = readable
		self.writeable = writeable
		self.has_rx = has_rx
		self.has_sub_rx = has_sub_rx
		self.param_count = param_count

	def total_params(self):
		params = self.param_count
		if self.has_rx:
			params += 1
		if self.has_sub_rx:
			params += 1
		return params

class TciEventType(Enum):
	COMMAND = 0
	PARAM_CHANGED = 1
	DATA_RECEIVED = 2

class TciEvent:
	def __init__(self, cmd_info, event_type, rx = -1, sub_rx = -1):
		self.cmd_info = cmd_info
		self.event_type = event_type
		self.rx = rx
		self.sub_rx = sub_rx

	def __repr__(self):
		if self.event_type == TciEventType.COMMAND:
			disp_type = "Command      "
		elif self.event_type == TciEventType.PARAM_CHANGED:
			disp_type = "Param_Changed"
		else:
			return f"Data_Received: (RX{self.rx})      {self.cmd_info}"

		if self.cmd_info.has_rx:
			rx_spec = f"(RX{self.rx}"
			if self.cmd_info.has_sub_rx:
				rx_spec += f", CH{self.sub_rx})"
			else:
				rx_spec += ")     "
		else:
			rx_spec = "          "

		return f"{disp_type}: {rx_spec} {self.cmd_info.name}"

	def get_value(self, param_dict):
		if self.event_type != TciEventType.PARAM_CHANGED:
			return None

		if not self.cmd_info.has_rx:
			return param_dict["system"][self.cmd_info.name]
		if not self.cmd_info.has_sub_rx:
			return param_dict["receivers"][self.rx][self.cmd_info.name]
		return param_dict["receivers"][self.rx]["channels"][self.sub_rx][self.cmd_info.name]

_COMMANDS = {cmd.name: cmd for cmd in [
	_TciCommand("CW_MACROS",             readable = False, has_rx = True),
	_TciCommand("CW_MSG",                readable = False, has_rx = True, param_count = 3),
	_TciCommand("CW_TERMINAL",           readable = False),
	_TciCommand("CW_MACROS_EMPTY",       readable = False, writeable = False, param_count = 0),
	_TciCommand("CALLSIGN_SEND",         readable = False, writeable = False),
	_TciCommand("CW_MACROS_STOP",        readable = False, param_count = 0),
	_TciCommand("VFO_LIMITS",            readable = False, writeable = False, param_count = 2),
	_TciCommand("IF_LIMITS",             readable = False, writeable = False, param_count = 2),
	_TciCommand("TRX_COUNT",             readable = False, writeable = False), 
	_TciCommand("CHANNELS_COUNT",        readable = False, writeable = False), 
	_TciCommand("DEVICE",                readable = False, writeable = False), 
	_TciCommand("RECEIVE_ONLY",          readable = False, writeable = False), 
	_TciCommand("MODULATIONS_LIST",      readable = False, writeable = False, param_count = -1),
	_TciCommand("TX_ENABLE",             readable = False, writeable = False, has_rx = True),
	_TciCommand("READY",                 readable = False, writeable = False, param_count = 0),
	_TciCommand("TX_FOOTSWITCH",         writeable = False, has_rx = True),
	_TciCommand("START",                 param_count = 0),
	_TciCommand("STOP",                  param_count = 0),
	_TciCommand("DDS",                   has_rx = True),
	_TciCommand("IF",                    has_rx = True, has_sub_rx = True),
	_TciCommand("RIT_ENABLE",            has_rx = True),
	_TciCommand("MODULATION",            has_rx = True),
	_TciCommand("RX_ENABLE",             has_rx = True),
	_TciCommand("XIT_ENABLE",            has_rx = True),
	_TciCommand("SPLIT_ENABLE",          has_rx = True),
	_TciCommand("RIT_OFFSET",            has_rx = True),
	_TciCommand("XIT_OFFSET",            has_rx = True),
	_TciCommand("RX_CHANNEL_ENABLE",     has_rx = True, has_sub_rx = True),
	_TciCommand("RX_FILTER_BAND",        has_rx = True, param_count = 2),
	_TciCommand("RX_SMETER",             has_rx = True, has_sub_rx = True),
	_TciCommand("CW_MACROS_SPEED"),
	_TciCommand("CW_MACROS_SPEED_UP",    readable = False),
	_TciCommand("CW_MACROS_SPEED_DOWN",  readable = False),
	_TciCommand("CW_MACROS_DELAY"),
	_TciCommand("TUNE",                  has_rx = True),
	_TciCommand("IQ_START",              has_rx = True, param_count = 0),
	_TciCommand("IQ_STOP",               has_rx = True, param_count = 0),
	_TciCommand("IQ_SAMPLERATE"),
	_TciCommand("AUDIO_START",           has_rx = True, param_count = 0),
	_TciCommand("AUDIO_STOP",            has_rx = True, param_count = 0),
	_TciCommand("AUDIO_SAMPLERATE"),
	_TciCommand("SPOT",                  readable = False, param_count = 5),
	_TciCommand("SPOT_DELETE",           readable = False),
	_TciCommand("SPOT_CLEAR",            readable = False, param_count = 0),
	_TciCommand("PROTOCOL",              readable = False, writeable = False, param_count = 2),
	_TciCommand("TX_POWER",              writeable = False),
	_TciCommand("TX_SWR",                writeable = False),
	_TciCommand("VOLUME"),
	_TciCommand("SQL_ENABLE",            has_rx = True),
	_TciCommand("SQL_LEVEL",             has_rx = True),
	_TciCommand("VFO",                   has_rx = True, has_sub_rx = True),
	_TciCommand("APP_FOCUS",             writeable = False),
	_TciCommand("SET_IN_FOCUS",          readable = False, param_count = 0),
	_TciCommand("MUTE"),
	_TciCommand("RX_MUTE",               has_rx = True),
	_TciCommand("CTCSS_ENABLE",          has_rx = True),
	_TciCommand("CTCSS_MODE",            has_rx = True),
	_TciCommand("CTCSS_RX_TONE",         has_rx = True),
	_TciCommand("CTCSS_TX_TONE",         has_rx = True),
	_TciCommand("CTCSS_LEVEL",           has_rx = True),
	_TciCommand("ECODER_SWITCH_RX",      has_rx = True),
	_TciCommand("ECODER_SWITCH_CHANNEL", has_rx = True),
	_TciCommand("RX_VOLUME",             has_rx = True, has_sub_rx = True),
	_TciCommand("RX_BALANCE",            has_rx = True, has_sub_rx = True),
	_TciCommand("TRX",                   has_rx = True),
	_TciCommand("DRIVE",                 has_rx = True),
	_TciCommand("TUNE_DRIVE",            has_rx = True),
	_TciCommand("RX_SENSORS_ENABLE",     readable = False, param_count = 2),
	_TciCommand("TX_SENSORS_ENABLE",     readable = False, param_count = 2),
	_TciCommand("RX_SENSORS",            readable = False, writeable = False, has_rx = True),
	_TciCommand("TX_SENSORS",            readable = False, writeable = False, has_rx = True),
	_TciCommand("RX_NB_ENABLE",          has_rx = True),
	_TciCommand("RX_NB_PARAM",           has_rx = True, param_count = 2),
	_TciCommand("RX_BIN_ENABLE",         has_rx = True),
	_TciCommand("RX_NR_ENABLE",          has_rx = True),
	_TciCommand("RX_ANC_ENABLE",         has_rx = True),
	_TciCommand("RX_ANF_ENABLE",         has_rx = True),
	_TciCommand("RX_APF_ENABLE",         has_rx = True),
	_TciCommand("RX_DSE_ENABLE",         has_rx = True),
	_TciCommand("RX_NF_ENABLE",          has_rx = True),
	_TciCommand("TX_FREQUENCY",          writeable = False),
	# Below are not in TCI 1.6 spec document but are sent in TCI 1.9 init.
	_TciCommand("MON_VOLUME"),
	_TciCommand("MON_ENABLE"),
	_TciCommand("DIGL_OFFSET"),
	_TciCommand("DIGU_OFFSET"),
	_TciCommand("AGC_MODE",              has_rx = True),
	_TciCommand("AGC_GAIN",              has_rx = True),
	_TciCommand("LOCK",                  has_rx = True),
	_TciCommand("CW_KEYER_SPEED"),
	_TciCommand("AUDIO_STREAM_SAMPLE_TYPE"),
	_TciCommand("AUDIO_STREAM_CHANNELS"),
]}

class TciDataType(Enum):
	IQ_STREAM = 0
	RX_AUDIO_STREAM = 1
	TX_AUDIO_STREAM = 2
	TX_CHRONO = 3

class TciDataPacket:
	def __init__(self, rx, sample_rate, data_format, codec, crc, length, data_type, channels, data):
		self.rx = rx
		self.sample_rate = sample_rate
		self.data_format = data_format
		self.codec = codec
		self.crc = crc
		self.length = length
		self.data_type = data_type
		self.channels = channels
		self.data = data

	@classmethod
	def from_buf(cls, buf):
		vals = struct.unpack_from("<8I", buf)
		rx = vals[0]
		sample_rate = vals[1]
		data_format = vals[2]
		codec = vals[3]
		crc = vals[4]
		length = vals[5]
		data_type = vals[6]
		channels = vals[7]
		offset = 8*4+8*4
		if length:
			data = array.array('f', buf[offset:])
		else:
			data = None
		return cls(rx, sample_rate, data_format, codec, crc, length, data_type, channels, data)
	
	def to_bytes(self):
		return struct.pack(f"<8I32x{4*self.length}s", self.rx, self.sample_rate, self.data_format, self.codec, self.crc, self.length, self.data_type, self.channels, self.data)
