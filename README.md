# eesdr-tci

Python package to interact with Expert Electronics SDR TCI control interface.

This package is a work-in-progress and will probably change quite a bit in the near term.

It is currently based on the [Protocol TCI.pdf, version 1.9](https://github.com/ExpertSDR3/TCI/blob/b3c46e14e829bac7dd4a9a749ce05556b874b569/Protocol%20TCI.pdf) from the ExpertSDR3/TCI documentation repo.

I have tested basic connectivity, receiving and changing parameters, and receiving and transmitting audio streams in various formats.

Until everything stabilizes, take a look at the [example](https://github.com/ars-ka0s/eesdr-tci/tree/main/example) folder to see a couple different ways it can be used. Example utilities include:
* `json_dump.py`: reads startup parameters and outputs them as a JSON dictionary
* `param_listener.py`: prints out all parameter changes received from the TCI server
* `receive_audio.py`: receives audio stream from the TCI interface which can be piped to other utilities
* `spot_saved_stations.py`: repeatedly spots a list of stations to keep them visible in the EESDR interface
* `scanner.py`: moves between a list of stations and pauses if squelch is broken
* `direwolf_interface.py`: provides a pure TCI interface to the [direwolf](https://github.com/wb2osz/direwolf) packet soundmodem. (Note: currently, this requires building a modified version which can pipe the transmit audio, see [this branch](https://github.com/ars-ka0s/direwolf/tree/stdout-audio) if interested.)
* `ctcss_decode.py`: listens for CTCSS/PL tones in receiver audio and prints possible matches.
