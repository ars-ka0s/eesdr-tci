# eesdr-tci

Python package to interact with Expert Electronics SDR TCI control interface.

This package is a work-in-progress and will probably change quite a bit in the near term.

It is currently based on the [TCI Protocol.pdf, version 2.0](https://github.com/ExpertSDR3/TCI/blob/b081213ff97150fd29f669c633f060f93c81a286/TCI%20Protocol.pdf) from the ExpertSDR3/TCI documentation repo.

I have tested basic connectivity, receiving and changing parameters, and receiving and transmitting audio streams in various formats.

Until everything stabilizes, take a look at the [example](https://github.com/ars-ka0s/eesdr-tci/tree/main/example) folder to see a couple different ways it can be used. Example utilities include:
* `json_dump.py`: reads startup parameters and outputs them as a JSON dictionary
* `param_listener.py`: prints out all parameter changes received from the TCI server
* `receive_audio.py`: receives audio stream from the TCI interface which can be piped to other utilities
* `spot_saved_stations.py`: repeatedly spots a list of stations to keep them visible in the EESDR interface
* `scanner.py`: moves between a list of stations and pauses if squelch is broken
* `direwolf_interface.py`: provides a pure TCI interface to the [direwolf](https://github.com/wb2osz/direwolf) packet soundmodem. (Note: currently, this requires building a modified version which can pipe the transmit audio, see [this branch](https://github.com/ars-ka0s/direwolf/tree/stdout-audio) if interested.)
* `ctcss_decode.py`: listens for CTCSS/PL tones in receiver audio and prints possible matches.
* `cw_macro_keyer.py`: 12-button CW macro keyer with freeform text box and speed adjustment.
![cw_macro_keyer_screenshot](https://github.com/ars-ka0s/eesdr-tci/assets/26339355/f0f62cdf-df23-4ae8-964d-130457132516)
* `contest_memo.py`: Use the spotting feature to leave notes to yourself during unassissted contest activites.
![contest_memo_screenshot](https://github.com/ars-ka0s/eesdr-tci/assets/26339355/f4114a63-4407-4760-939b-192a45bfb3ae)

### Recent Changes

##### v0.0.2
Updated/added a couple of commands to match the most recent TCI protocol definition.

##### v0.1.0
Refactored several things, including coding style cleanups and adding docstrings to the code.
There were two major changes that may impact existing code:
1. Module name tci.Listener was changed to tci.listener.
2. Listener.get_cached_param_value(...) was removed along with the entire caching setup.
It was mainly a remnant of my very first pass at structuring things and I didn't find a need for it in any of the utilities I've made so far.
It could also be easily recreated in a program that would make use of it.