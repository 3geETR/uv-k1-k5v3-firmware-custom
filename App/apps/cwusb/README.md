# CW USB overlay app

CW USB keys an A1A-style carrier on the current TX VFO using a straight key
or paddle on USB-C. It shares its source with CW Keyer, whose PTT/SIDE-key
binary remains unchanged. The VFO must be in FM; the receiving station needs
CW or SSB to hear an unmodulated carrier.

## Requirements and build

Use overlay ABI 1 / API level 3 with the silent `tx_prepare` service (table
size at least 368 bytes). Older tables fail closed. No resident changes are
required. From the repository root, run `./compile-app.sh cwusb`; the output
is `build/Apps/CWUSB.app`. Use a free application slot for experiments.
The existing ARM GCC 13.3.rel1 build uses a 4096-byte overlay; this arming-only
step occupies 3916 bytes. Stack usage is outside that figure.

## Deliberate arming, once per launch

At launch the padlock is shown and TX, including PTT, is locked. First leave
both USB contacts and PTT released for at least 20 ms. Then hold the straight
key TIP contact in STRAIGHT, or both paddle contacts together in PADDLE, for
five continuous seconds. Releasing early restarts qualification.

The existing Ready check appears as soon as five seconds qualify, even if
the contacts stay held. It certifies the hold, not permission to transmit.
Release ALL contacts and PTT for at least 20 ms before normal keying is
allowed. There is no carrier during this gesture. Once operational, the app
stays armed across RX/TX changes; closing and reopening requires a new gesture.
Arming is never stored. Timing uses the existing 48 MHz API clock, not loop
counts; an observed sampling gap longer than 50 ms restarts qualification.

The first detected/qualified keying request after RX is no longer consumed
by the former preparation-only press and 300-service-pass holdoff. Silent
`tx_prepare`, TX permission checks, PA ramps and the mark-duration protection
remain. After a duration-limit refusal, the stale debounced contact is cleared
on release so it cannot restart TX without a fresh valid contact.

## Controls

- `PTT`: straight key after arming, in either input mode.
- USB D+ / TIP: straight key in STRAIGHT, dit in PADDLE.
- USB D- / RING: dah in PADDLE.
- `1`: STRAIGHT / PADDLE; `5`: reverse dit/dah.
- `0`: receive speaker; `2`: WPM; `3`: RX pitch; `4`: break-in; `6`: XTAL.
- `F`, then `2`, `3`, `4`, or `6`: decrease the corresponding setting.
- `UP` / `DOWN`: local tuning in 100 Hz steps, up to +/-50 kHz.
- `MENU`: help; `EXIT`: close. EXIT works during arming. In STRAIGHT,
  a held keying control can take priority until released; do not treat EXIT
  as a separately validated emergency RF cutoff.

## Adapter and configuration

![USB-C paddle adapter wiring](usbc-paddle-wiring.svg)

D+ (PA12) goes to TIP, D- (PA11) to RING and GND to SLEEVE; contacts close to
ground. Leave VBUS, CC and shield insulated and unconnected. Never connect
this adapter to a charger or PC. The app saves/restores its USB pin/clock bits;
there is no PC link while it is open. No CC-based cable detection is attempted.

Both contacts must read open during the initial/final release. Unlike the
old STRAIGHT behavior, a mono plug grounding RING cannot complete this gesture.
A contact already closed on launch or never released cannot arm. A short
appearing after initial release, lasting five seconds and then disappearing
cannot be distinguished from a deliberate gesture by software alone.

Settings use the existing 12-byte layout and the installed slot's configuration,
tagged by app name. Preserve settings before replacing an app in the same slot;
CW Keyer and CW USB have different names. Arming is RAM-only.

## Validation and remaining limits

Run the host checks after generating assets with the normal build:

```sh
python App/apps/cwusb/test/arming.py
```

Python 3 and a C11 host compiler are required; `HOST_CC` overrides `gcc`.
The 41 checks cover the two inputs, real-time qualification, long squeeze,
release gating, API/TX refusal, RX/TX cycles, short requests, EXIT and the
STRAIGHT limit/release regression. The host substitutes GPIO/API callbacks;
it cannot validate physical RF or electrical contacts.

The board may mask contacts briefly after inactivity, and the existing
STRAIGHT filter can miss very short pulses. Removing the repeated arming
press does not prove those electrical effects or RF preparation latency have
disappeared. The S-meter and receive-audio transitions remain; periodic RSSI
reads are suspended while locked and resume when operational.

The final combined development was hardware-tested by F4LPF on UV-K5 V3 with
Labs API3 at 494bc6af. Arming, mode display/selection, CW and IAMB A squeeze
were satisfactory. This intermediate arming-only commit was tested on host,
not independently on hardware; RF validation is not exhaustive. For the
original adapter implementation and hardware record see [PR #665](https://github.com/armel/uv-k1-k5v3-firmware-custom/pull/665)
and the sibling [CW Keyer README](../cwkeyer/README.md).

Functional design, USB-C cable and hardware testing: F4LPF. Implementation and
software tests: OpenAI Codex. Technical assistance and contribution preparation:
ChatGPT. Existing project and USB-input authorship notices are retained.
