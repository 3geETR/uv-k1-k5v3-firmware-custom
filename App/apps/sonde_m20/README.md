# SONDE M20: on-radio Meteomodem M20 decoder

Goal: an overlay app that decodes Meteomodem M20 radiosonde frames on the
UV-K1 / UV-K5 v3 and shows the serial number, GPS position, altitude,
temperature and pressure when present.

Status:

| Step | State |
|---|---|
| Audio path an app can sample (PA4 ADC) | **Done** (same path as EPIRB 406 / APRS RX) |
| Softin + checkM10 decoder (`decm20.c`), host-tested | **Done** (`test/run_tests.sh`) |
| AF bypass (REG_47 AF=9) required for 9600-chip Manchester | **Done** — stock FM AF low-passes ~3–4 kHz and wipes 1-chip runs |
| Mid-sample DPLL (2 ADC samples/chip @ 19.2 kHz) | **Done** — needed for real UV-K1 captures (~9620 chip/s) |
| Radio app (`sonde_m20_app.c`) | **v0.50** decodes a live M20 on a UV-K1 (ID, lat/lon, alt, T, P) |

## Using the app

1. Set the VFO to the sonde frequency, **FM, wide bandwidth** (e.g. 432.500 MHz
   for a stock M20 on 70 cm).
2. Launch **SONDE M20**. The speaker is off by default; decoding uses the BK4829
   AF output on PA4 either way.
3. Default front-end attenuator is **27 dB** (A27). If the sonde is very close
   and frames fail, raise ATT further with key `3` or the `*` menu. Avoid
   `BYP+` (maximum gain) on a strong signal.

| Screen | Content |
|---|---|
| Status bar | `SONDE M20` title, `WAIT` capsule until the first CRC-OK frame, speaker icon while the speaker is on |
| Fixed line 0 | Serial number in bold (`YMM-n-bnnnn`, same form as auto_rx / SondeHub) |
| Body | Latitude / longitude; `ALT …m`; `T …C` and pressure in hPa when available |
| Dotted separator | Line at y=40 |
| Fixed rows | RX frequency (and ±5 kHz offset), live RSSI; `FRAME n` and current ATT |

Keys (UV-K5 and UV-K1):

| Key | Action |
|---|---|
| 1 | Speaker on/off, saved on exit |
| 3 | Cycle front-end attenuator (0 / 6 / 15 / 27 dB / BYP / BYP+) |
| `*` | Parameters: Speaker and ATT (UP/DOWN select the row, `*` changes the value, EXIT/MENU closes) |
| 4 / 6 | Tune −5 / +5 kHz from the VFO, up to ±50 kHz |
| 5 | Back to the VFO frequency |
| EXIT | Quit (frequency offset restored) |

## Signal path on the radio

```
M20 RF --> BK4829 (RAW: no HPF300 / LPF3K / de-emphasis; REG_43 wide)
       --> AF output mode 9 (bypass) --> audio circuit --> PA4
       --> ADC ch4 @ 19.2 kHz (2 samples per Manchester chip)
```

- **RAW receive** is set by the app (REG_2B bits 10/9/8, REG_73 bit 4).
- **AF=9 (bypass)** is mandatory. With the normal FM AF path the BK4829 audio
  is low-passed around 3–4 kHz. M20 Manchester at 9600 chips/s needs ~10 kHz of
  AF bandwidth; without bypass, 1-chip runs disappear, the `0x4520` head may
  still lock, and the CRC always fails.
- **REG_43** is forced to the widest IF filter for the session and restored on
  exit.
- **PA4 bias**: the app holds the pin at mid-scale with the MCU DAC (buffer off,
  code 2048), same approach as EPIRB 406.
- While a frame is being collected (`ST_DATA`), the app does not poll the keypad
  or refresh the LCD: a key scan is far longer than the 52 µs sample budget.

## Decoder (`decm20.c`)

Streaming, one call per ADC sample, integer only, freestanding. Follows
auto_rx `m20mod` softin:

1. **DC removal**: exponential mean, frozen while a frame is in progress so bias
   drift does not corrupt late bits.
2. **Chip timing**: edge DPLL with mid-sample boundaries (the chip edge often
   falls between the two ADC samples). Zero crossings are interpolated.
3. **Search**: 32-chip rawheader `1001100…` soft correlation, then the next 32
   chips softin to `0x4520` / `0x4320` (body polarity probed via the MSB).
4. **Bits**: Manchester softin `(s2>=s1)`, differential vs previous man bit.
5. **Parse**: checkM10 CRC; SN; lat/lon ×1e6; altitude; thermistor ADC (table
   lookup in the app for °C); optional pressure (DF9DQ layout, FW ≥ 7).

## Tests (`test/`)

```
test/run_tests.sh
```

Needs a host C compiler (`gcc` or `clang`) and bash. Builds `host_decm20`, which
checks `decm20_parse` on a crafted CRC-valid frame and a full softin pass
(rawheader + body through `decm20_push`).

## Build

**Recommended (Windows / Linux / macOS):** Docker, same as the rest of the
firmware. From the repo root:

```bash
./compile-app.sh sonde_m20
```

Requires [Docker](https://docs.docker.com/get-docker/). The first run builds the
`uvk1-uvk5v3` image. The result is `build/Apps/SONDEM20.app` (≤ 4 KiB overlay).

On Windows use Git Bash, WSL, or any shell that can run the script and talk to
Docker Desktop — you do **not** need a local ARM GCC for this path.

**Optional native build** (no Docker): install

- [Arm GNU Toolchain](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)
  (`arm-none-eabi-gcc` / `objcopy` on `PATH`)
- Python 3

then from this directory:

```bash
./build.sh
```

On Windows, run that from Git Bash or MSYS2 so the script and toolchain agree
on paths. Copy the produced `SONDEM20.app` into the radio’s Apps slot with your
usual flash tool.

**Host tests only** (no cross-compiler):

```bash
test/run_tests.sh
```

## Version

`APP_VER` in `build.sh` is bumped for every build that goes on a radio and is
stored in the `.app` metadata. The status-bar title stays `SONDE M20`.
Current: **v0.50**.
