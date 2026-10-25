# Data sources and provenance

## Archived real recording

- Observation: SatNOGS 6659851, FUNCUBE-1, NORAD 39444
- Observation page: `https://network.satnogs.org/observations/6659851/`
- Original API response: `data/real/satnogs_6659851_observation.json`
- Original OGG: `data/real/satnogs_6659851_2022-10-26T04-12-41.ogg`
- Manifest: `data/real/satnogs_6659851_manifest.json`
- OGG SHA-256: `c317e44ccddb890023a1b863c326fb856525902da3aeefa3355d566fe64aaf63`
- API JSON SHA-256: `e47c5a0ef8faeac94dd03fcd76d796a5a1811132b98adc7828edb8ac310246f0`
- License/attribution: SatNOGS Network observation data, CC BY-SA 4.0;
  ground station PE0SAT-32

Acquisition began `2022-10-26T04:12:41Z` at 51.721268 N, 5.029 E,
5 m altitude. The documented transmitter is 145.935 MHz, BPSK 1200 baud.
The exact historical FUNCUBE-1 TLE in the observation record has epoch
2022 day 298.34474311 and is evaluated at the recording timestamps.

SoundFile inspection confirms mono OGG/Vorbis, 48 kHz, 16,934,208 decoded
samples, and 352.796 seconds. SatNOGS client metadata reports an RTL-SDR at
2.048 MS/s, 42.1 dB gain and −1 ppm correction. SatNOGS flowgraph tag 2.3
`generic/bpsk.grc` confirms that the target is dynamically Doppler-corrected,
rotated to a 12 kHz audio IF, converted from complex to its real component,
and encoded to OGG. The archive is therefore real received audio but not raw
RF I/Q. Values are normalized lossy decoder amplitude, not calibrated power.

The decoded audio is 3.204 seconds shorter than the scheduled observation;
LastPing uses the actual decoded duration and does not invent samples. Three
incorrect candidates use historical TLEs retained by adjacent SatNOGS records:
OSCAR 11 from observation 6659848, AAUSAT CUBESAT 2 from 6659850, and OSCAR 7
from 6659856. All are below the PE0SAT-32 horizon during this recording.

SatNOGS lists 53 timestamped decoded-frame artifacts for observation 6659851,
which independently supports a positive reception. The schedule label alone is
not passed into ranking or treated as proof. No verified real negative corpus
is included; real false-alarm rate is not measured.

References inspected:

- `https://wiki.satnogs.org/Artifacts`
- `https://wiki.satnogs.org/Wiki/Replay_observations_from_audio`
- `https://gitlab.com/librespacefoundation/satnogs/satnogs-flowgraphs/-/blob/2.3/generic/bpsk.grc`
- `https://network.satnogs.org/about/`

## Synthetic experiment orbital elements

- Provider: CelesTrak public GP endpoint
- Exact URL: `https://celestrak.org/NORAD/elements/gp.php?GROUP=CUBESAT&FORMAT=TLE`
- Cached original response: `data/celestrak_cubesat.tle`
- Cache metadata: `data/celestrak_cubesat_metadata.json`

The checked cache was retrieved at `2026-10-25T11:42:39.347900+00:00`.
The pass selector chose **CUTE-1 (CO-55), NORAD 27844**, with orbital epoch
`2026-10-24T06:58:10.101196+00:00`. The application reports cache age and
warns when the elements are more than 14 days from the simulated recording.
The selected replay begins at `2026-10-25T13:57:08.563252+00:00`; both this
time and the orbital epoch are surfaced by the backend and interface.
The orbital elements identify the geometry source only; the app does not imply
that CUTE-1 is missing or that its transmitter metadata was verified.

Skyfield evaluates the TLE with SGP4 and no planetary ephemeris. The observer
is Berkeley, California (37.8715 N, 122.2730 W, 52 m). Range rate is in km/s.
For the assumed 437 MHz carrier, Doppler uses
`delta_f = -f0 * range_rate / c`; positive (receding) range rate produces a
negative offset.

## Synthetic radio and evaluation data

All 128 by 192 power arrays are locally generated synthetic spectra. They
include exponential background power, a finite-width intermittent beacon,
stationary interference, unrelated drifting signals, and bounded
time/frequency mismatch. No recorded I/Q or real RF observation is included.
Training, validation, and test seeds are disjoint and recorded in the model and
benchmark metadata.

