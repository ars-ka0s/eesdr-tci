"""The tci module contains the constants, classes, and enums used to format commands and interact
with TCI audio and data streams.
"""

from enum import IntEnum
import struct

class TciCommand:
    """TciCommand instances define the individual commands that can be sent to or received from a
    TCI server and are used to check parameters and produce command strings.  The COMMANDS dict
    contains preconfigured TciCommand instances for currently-known commands retrievable by their
    name as key.
    """

    def __init__(self, name, readable = True, writeable = True,
                 has_rx = False, has_sub_rx = False, param_count = 1):
        self.name = name
        self.readable = readable
        self.writeable = writeable
        self.has_rx = has_rx
        self.has_sub_rx = has_sub_rx
        self.param_count = param_count

    def total_params(self):
        """Return the total number of parameters that should be present in a command string."""
        params = self.param_count
        if self.has_rx:
            params += 1
        if self.has_sub_rx:
            params += 1
        return params

    def prepare_string(self, action, rx = None, sub_rx = None, params = (), check_params = True):
        """Prepares a command string for sending using the provided values & parameters."""
        uc_command = self.name.upper()

        if action == TciCommandSendAction.READ and not self.readable:
            raise ValueError(f"Command {uc_command} not readable.")

        if action == TciCommandSendAction.WRITE and not self.writeable:
            raise ValueError(f"Command {uc_command} not writeable.")

        if self.has_rx:
            try:
                rx = int(rx)
                assert rx >= 0
            except (TypeError, ValueError, AssertionError) as exc:
                raise ValueError(f"Command {uc_command} requires specifying applicable receiver number (nonnegative integer)") from exc

        if self.has_sub_rx:
            try:
                sub_rx = int(sub_rx)
                assert sub_rx  >= 0
            except (TypeError, ValueError, AssertionError) as exc:
                raise ValueError(f"Command {uc_command} requires specifying applicable sub-receiver/channel number (nonnegative integer)") from exc

        if check_params:
            if action == TciCommandSendAction.READ and self.param_count > 0:
                expected = self.param_count - 1
            else:
                expected = self.param_count

            if len(params) != expected:
                raise ValueError(f"Command {uc_command} requires {expected} additional parameters to {action.name}, {len(params)} given.")

        cmd_params = []
        if self.has_rx:
            cmd_params += [str(rx)]
        if self.has_sub_rx:
            cmd_params += [str(sub_rx)]
        cmd_params += [str(p) for p in params]

        if len(cmd_params) == 0:
            return f"{uc_command};"

        param_str = ",".join(cmd_params)
        return f"{uc_command}:{param_str};"

COMMANDS = {cmd.name: cmd for cmd in [
    # Initialization Type Commands - TCI Protocol 2.0 - Section 4.1
    # All these should be readable = False, writeable = False
    TciCommand("VFO_LIMITS",              readable = False, writeable = False, param_count = 2),
    TciCommand("IF_LIMITS",               readable = False, writeable = False, param_count = 2),
    TciCommand("TRX_COUNT",               readable = False, writeable = False),
    TciCommand("CHANNELS_COUNT",          readable = False, writeable = False),
    TciCommand("DEVICE",                  readable = False, writeable = False),
    TciCommand("RECEIVE_ONLY",            readable = False, writeable = False),
    TciCommand("MODULATIONS_LIST",        readable = False, writeable = False, param_count = -1),
    TciCommand("PROTOCOL",                readable = False, writeable = False, param_count = 2),
    TciCommand("READY",                   readable = False, writeable = False, param_count = 0),
    # Bidirectional Control Commands - TCI Protocol 2.0 - Section 4.2
    # All these should be readable = True, writeable = True
    TciCommand("START",                   readable = False, param_count = 0),
    TciCommand("STOP",                    readable = False, param_count = 0),
    TciCommand("DDS",                     has_rx = True),
    TciCommand("IF",                      has_rx = True, has_sub_rx = True),
    TciCommand("VFO",                     has_rx = True, has_sub_rx = True),
    TciCommand("MODULATION",              has_rx = True),
    TciCommand("TRX",                     has_rx = True), # has optional parameter for TCI audio only for sending
    TciCommand("TUNE",                    has_rx = True),
    TciCommand("DRIVE",                   has_rx = True),
    TciCommand("TUNE_DRIVE",              has_rx = True),
    TciCommand("RIT_ENABLE",              has_rx = True),
    TciCommand("XIT_ENABLE",              has_rx = True),
    TciCommand("SPLIT_ENABLE",            has_rx = True),
    TciCommand("RIT_OFFSET",              has_rx = True),
    TciCommand("XIT_OFFSET",              has_rx = True),
    TciCommand("RX_CHANNEL_ENABLE",       has_rx = True, has_sub_rx = True),
    TciCommand("RX_FILTER_BAND",          has_rx = True, param_count = 2),
    TciCommand("CW_MACROS_SPEED"),
    TciCommand("CW_MACROS_DELAY"),
    TciCommand("CW_KEYER_SPEED"),
    TciCommand("VOLUME"),
    TciCommand("MUTE"),
    TciCommand("RX_MUTE",                 has_rx = True),
    TciCommand("RX_VOLUME",               has_rx = True, has_sub_rx = True),
    TciCommand("RX_BALANCE",              has_rx = True, has_sub_rx = True),
    TciCommand("MON_VOLUME"),
    TciCommand("MON_ENABLE"),
    TciCommand("AGC_MODE",                has_rx = True),
    TciCommand("AGC_GAIN",                has_rx = True),
    TciCommand("RX_NB_ENABLE",            has_rx = True),
    TciCommand("RX_NB_PARAM",             has_rx = True, param_count = 2),
    TciCommand("RX_BIN_ENABLE",           has_rx = True),
    TciCommand("RX_NR_ENABLE",            has_rx = True),
    TciCommand("RX_ANC_ENABLE",           has_rx = True),
    TciCommand("RX_ANF_ENABLE",           has_rx = True),
    TciCommand("RX_APF_ENABLE",           has_rx = True),
    TciCommand("RX_DSE_ENABLE",           has_rx = True),
    TciCommand("RX_NF_ENABLE",            has_rx = True),
    TciCommand("LOCK",                    has_rx = True),
    TciCommand("SQL_ENABLE",              has_rx = True),
    TciCommand("SQL_LEVEL",               has_rx = True),
    TciCommand("DIGL_OFFSET"),
    TciCommand("DIGU_OFFSET"),
    # Unidirectional Control Commands - TCI Protocol 2.0 - Section 4.3
    # All these should be readable = False, writeable = True/False depending on semantics
    TciCommand("TX_ENABLE",               readable = False, writeable = False, has_rx = True),
    TciCommand("CW_MACROS_SPEED_UP",      readable = False),
    TciCommand("CW_MACROS_SPEED_DOWN",    readable = False),
    TciCommand("SPOT",                    readable = False, param_count = 5),
    TciCommand("SPOT_DELETE",             readable = False),
    TciCommand("IQ_SAMPLERATE",           readable = False),
    TciCommand("AUDIO_SAMPLERATE",        readable = False),
    TciCommand("IQ_START",                readable = False, has_rx = True, param_count = 0),
    TciCommand("IQ_STOP",                 readable = False, has_rx = True, param_count = 0),
    TciCommand("AUDIO_START",             readable = False, has_rx = True, param_count = 0),
    TciCommand("AUDIO_STOP",              readable = False, has_rx = True, param_count = 0),
    TciCommand("LINE_OUT_START",          readable = False, has_rx = True, param_count = 0),
    TciCommand("LINE_OUT_STOP",           readable = False, has_rx = True, param_count = 0),
    TciCommand("LINE_OUT_RECORDER_START", readable = False, has_rx = True),
    TciCommand("LINE_OUT_RECORDER_SAVE",  readable = False, has_rx = True),
    TciCommand("LINE_OUT_RECORDER_BREAK", readable = False, has_rx = True, param_count = 0),
    TciCommand("SPOT_CLEAR",              readable = False, param_count = 0),
    TciCommand("AUDIO_STREAM_SAMPLE_TYPE",readable = False),
    TciCommand("AUDIO_STREAM_CHANNELS",   readable = False),
    TciCommand("AUDIO_STREAM_SAMPLES",    readable = False),
    TciCommand("TX_STREAM_AUDIO_BUFFERING", readable = False),
    # Notification Commands - TCI Protocol 2.0 - Section 4.4
    # All these should be readable = False, writeable = False, but a few commands are mixed into this section
    TciCommand("CLICKED_ON_SPOT",         readable = False, writeable = False, param_count = 2),
    TciCommand("RX_CLICKED_ON_SPOT",      readable = False, writeable = False, has_rx = True, has_sub_rx = True, param_count = 2),
    TciCommand("TX_FOOTSWITCH",           readable = False, writeable = False, has_rx = True),
    TciCommand("TX_FREQUENCY",            readable = False, writeable = False),
    TciCommand("APP_FOCUS",               readable = False, writeable = False),
    TciCommand("SET_IN_FOCUS",            readable = False, param_count = 0),
    TciCommand("KEYER",                   readable = False, writeable = False, has_rx = True),
    TciCommand("RX_SENSORS_ENABLE",       readable = False, param_count = 2),
    TciCommand("TX_SENSORS_ENABLE",       readable = False, param_count = 2),
    TciCommand("RX_SENSORS",              readable = False, writeable = False, has_rx = True), # Deprecated in 2.0
    TciCommand("TX_SENSORS",              readable = False, writeable = False, has_rx = True, param_count = 4),
    # New Commands - TCI Protocol 2.0 - Section 4.5
    TciCommand("VFO_LOCK",                readable = False, writeable = False, has_rx = True, has_sub_rx = True),
    TciCommand("RX_CHANNEL_SENSORS",      readable = False, writeable = False, has_rx = True, has_sub_rx = True),
    # CW Macros - TCI Protocl 2.0 - Section 3.2.1
    TciCommand("CW_MACROS",               readable = False, has_rx = True),
    TciCommand("CW_TERMINAL",             readable = False),
    TciCommand("CW_MACROS_EMPTY",         readable = False, writeable = False, param_count = 0),
    TciCommand("CW_MSG",                  readable = False, has_rx = True, param_count = 3),
    TciCommand("CALLSIGN_SEND",           readable = False, writeable = False),
    TciCommand("CW_MACROS_STOP",          readable = False, param_count = 0),
    # Commands not documented in 1.9 but definitely encountered - TCI Protocol 1.6
    TciCommand("RX_ENABLE",               has_rx = True),
    TciCommand("CTCSS_ENABLE",            has_rx = True),
    TciCommand("CTCSS_MODE",              has_rx = True),
    TciCommand("CTCSS_RX_TONE",           has_rx = True),
    TciCommand("CTCSS_TX_TONE",           has_rx = True),
    TciCommand("CTCSS_LEVEL",             has_rx = True),
    # Commands not documented in 1.9 but no similar functionality - TCI Protocol 1.6
    TciCommand("ECODER_SWITCH_RX",        has_rx = True),
    TciCommand("ECODER_SWITCH_CHANNEL",   has_rx = True),
    # Commands not documented in 1.9 but probably superseded - TCI Protocol 1.6
    TciCommand("RX_SMETER",               writeable = False, has_rx = True, has_sub_rx = True),
    TciCommand("TX_POWER",                writeable = False),
    TciCommand("TX_SWR",                  writeable = False),
]}

class TciCommandSendAction(IntEnum):
    """TciCommandSendAction defines whether a parameter update is being requested (READ)
    or sent to the device (WRITE)."""
    READ = 0
    WRITE = 1

class TciStreamType(IntEnum):
    """TciStreamType defines the type of data stream contained in a data packet."""
    IQ_STREAM = 0
    RX_AUDIO_STREAM = 1
    TX_AUDIO_STREAM = 2
    TX_CHRONO = 3

class TciSampleType(IntEnum):
    """TciSampleType defines the type of individual samples of data contained in a data packet."""
    INT16 = 0
    INT24 = 1
    INT32 = 2
    FLOAT32 = 3

class TciDataPacket:
    """TciDataPacket instances are used to contain received data packets or define outgoing data packets.
    """

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
        """Produces a TciDataPacket instance by decoding a raw recevied data buffer."""
        vals = struct.unpack_from("<8I", buf)
        rx = vals[0]
        sample_rate = vals[1]
        data_format = TciSampleType(vals[2])
        codec = vals[3]
        crc = vals[4]
        length = vals[5]
        data_type = TciStreamType(vals[6])
        channels = vals[7]
        offset = 8*4+8*4
        if length:
            data = buf[offset:]
        else:
            data = None
        return cls(rx, sample_rate, data_format, codec, crc, length, data_type, channels, data)

    def to_bytes(self):
        """Returns the raw bytes required to represent a TciDataPacket instance."""
        if self.data_format == TciSampleType.INT16:
            bytes_per_sample = 2
        elif self.data_format == TciSampleType.INT24:
            bytes_per_sample = 3
        else:
            bytes_per_sample = 4
        return struct.pack(f"<8I32x{bytes_per_sample*self.length}s", self.rx, self.sample_rate, self.data_format, self.codec, self.crc, self.length, self.data_type, self.channels, self.data)
