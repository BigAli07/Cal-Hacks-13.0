# Bundled SatNOGS observation

This directory contains SatNOGS Network observation **6659851** and the
metadata required for reproducible offline replay.

- Copyright/attribution: SatNOGS Network contributors and ground station
  PE0SAT-32.
- License: Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0).
- Source observation: https://network.satnogs.org/observations/6659851/
- SatNOGS licensing statement: https://network.satnogs.org/about/

`satnogs_6659851_observation.json` is the untouched API response.
`satnogs_6659851_2022-10-26T04-12-41.ogg` is the untouched archived audio.
`satnogs_6659851_manifest.json` records hashes, interpretation, receiver and
transmitter metadata, historical candidate TLEs, and limitations.

The audio is a lossy, real-valued output of the GPL-3.0 SatNOGS BPSK
flowgraph. LastPing does not redistribute or copy flowgraph source code; the
source revision inspected for format interpretation is linked in the manifest.

## WAV compatibility test

`tests/test_real_data.py` decodes the licensed bundled OGG with libsndfile and
writes the same samples to an in-memory mono 48 kHz PCM-16 WAV. The test updates
only the temporary manifest's filename, container/codec description and
SHA-256, then runs that WAV through the full archived-recording pipeline. The
converted bytes are not committed. They remain a derivative of SatNOGS
observation 6659851 under the same CC BY-SA 4.0 attribution and are not a second
or independent observation. Separate generated WAVs verify that mismatched
sample rates and stereo channels are rejected before analysis.
