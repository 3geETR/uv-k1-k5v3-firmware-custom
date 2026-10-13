# POCSAG RX (overlay app)

Receives **POCSAG** pager transmissions at 1200 bauds, as the amateur
[DAPNET](https://hampager.de) network sends them, and shows the pages: address
(RIC), text, function.

## Status

| Part | State |
|---|---|
| Format (`test/pocsag.py`) | Self-tested: the sync and idle codewords come out of the BCH encoder, pages round-trip, one wrong bit per codeword is corrected, two are detected |
| Receive model (`test/model_rx.py`) | All test pages decoded for an audio high-pass anywhere from 10 Hz to 1 kHz (1.5 kHz without noise), with +-4 kHz offset, either polarity; nothing out of 2 x 60 s of noise. With a +1 % clock a junk page can slip in |
| Radio app (`pocsagrx_app.c`) | v0.1. On the radio (2026-10-13): with three feedback slicers only, the Flipper transmission was heard but **nothing decoded, not even a sync codeword** (`syn 0`); **with the hysteresis slicers added, all six Flipper files are decoded** (`alpha`, `numeric`, `two`, `long`, and `inverted` / `biterr`, which show the same page as `alpha` as they should). So the audio path cuts the low frequencies well above 300 Hz |
| On air | Not tested |

## The open question

POCSAG keys the carrier frequency with the bits themselves: the discriminator
outputs the bit stream, not tones, with runs of up to 13 equal bits (11 ms).
The radio's audio path cuts the low frequencies, and where it starts passing
with the filters off (RAW) was never measured. A high-passed level droops back
to zero during a run.

The decoder therefore runs five slicers of two kinds. Two put the baseline back
from their own decisions (quantized feedback): the best in noise, for a corner
up to about 300 Hz. Three flip their level on the pulse a change of level
leaves, and hold in between (hysteresis, thresholds at 1/8, 1/4 and 1/2 of the
peak): they do not care whether the level droops, and hold from 10 Hz to about
1.5 kHz. **A Flipper file on the radio tells whether the real path is inside
that range**: a page shown, or not.

Until a first page, the bottom line shows what the decoder sees:
`lvl 512 syn 3 ok 40 bad 8`: signal level of the first slicer, sync codewords
found, codewords good and bad, summed over the five slicers (key 2 resets
them). A whole `pocsag_alpha.sub` read by every slicer would give `syn 5`,
`ok 160`, `bad 0`.

## Use

1. Tune the VFO (FM, wide) to the pager frequency: **439.9875 MHz** for DAPNET
   where a transmitter is in range (see the coverage map on hampager.de), or
   **433.650 MHz** for the Flipper Zero bench files.
2. Launch POCSAG RX. Until a first page, the bottom line shows the decoder's
   counters (see above).

The screen follows APRS RX: the address in bold with the counters at its right
(pages received, page shown / pages kept), the text under it, the dotted
separator, the frequency in big digits, and the bottom line
`-89dBm  func 3  last 02m15`: level, function (0-3), time since the page came.

| Key | Action |
|---|---|
| UP / DOWN | Scroll the text a row when it overflows (normal view); at either end, the newer / older page (UV-K1: LEFT / RIGHT). 5 pages kept |
| * | Normal view (18 characters a row, 3 rows) / compact view (32 tiny characters a row: a whole 80-character page); saved |
| 1 | Speaker on / off (saved, off by default). Not gated by the squelch, as EPIRB 406: the hiss is heard between transmissions, and a transmission as the raw buzz it is |
| 2 | Clear |
| EXIT | Quit |

## Limits

- **1200 bauds only.** 512 bauds is not looked for; 2400 bauds needs more
  audio band than the radio has.
- **Function 0 is read as numeric, 1-3 as text**, the usual convention; a
  network using another one shows garbage for those pages.
- **A page stops at the first codeword that cannot be corrected** (two wrong
  bits or more): its end is lost, the next pages are not.
- **A page without text is not shown** (tone-only pages): a slicer that slipped
  a bit reads shifted codewords, which are often valid ones, and they come out
  as addresses without text. A junk page with a few characters can still get
  through now and then.
- **Long transmissions**: keys and screen are served between batches, or every
  2 s inside a long transmission. Each service costs about 15 bits: the page
  being received then is cut there. The codeword alignment is kept.
- Pages are kept in RAM only.

## Testing with a Flipper Zero

Here the Flipper sends the real thing: direct FSK, as a pager transmitter does
(+-2.38 kHz instead of +-4.5 kHz).

```sh
python3 test/flipper_pocsag.py test/flipper
```

| File | Expected on the radio |
|---|---|
| `pocsag_alpha.sub` | `1234567`, `F4HWN: POCSAG RX test on 433.650 MHz` |
| `pocsag_numeric.sub` | `1234560`, `0145 67-89`, func 0 |
| `pocsag_two.sub` | Two pages: `2504` and `165856` |
| `pocsag_long.sub` | `1000001`, a 72-character text (scroll, or `*`) |
| `pocsag_inverted.sub` | Same as alpha: the other discriminator polarity |
| `pocsag_biterr.sub` | Same as alpha: one wrong bit in every other codeword, corrected |

Copy them to `subghz/` on the SD card, tune the radio to 433.650 MHz FM, launch
POCSAG RX, open a file and press Send (1.5 s each). Start with `pocsag_alpha`:
if nothing shows, try `pocsag_inverted`; if neither does, the audio path cuts
too high for this decoder.

## How it decodes

PA4 audio on ADC channel 4 at 9.6 kHz (APRS RX's path), receiver in RAW
(EPIRB 406's setting, AFC off). DC removal, sum of 4 samples (half a bit), then
per slicer either `r = y + fb`, where `fb` follows the decided level times the
mean of `|r|` with a time constant of 32 or 16 samples, or a level that flips
when `y` passes a fraction of its peak; a DPLL on the changes of level; the
last 32 bits against the sync codeword `7CD215D8` and its
complement, two wrong bits allowed; then 16 codewords a batch, BCH (31,21)
checked from the syndrome with one bit corrected, and the next sync codeword.
An address opens a page, message codewords fill it, anything else closes it.
A slicer that just read a bad codeword is not trusted to correct the next
eight. The slicers give the same page: within 2 s, a page to the same address
replaces the one shown only when it is longer.

## Files

- `pocsagrx_app.c`, `gen_assets.py`, `build.sh`, `app.ld`: the app.
- `test/pocsag.py`: the format (encode, decode), self-tested.
- `test/flipper_pocsag.py`: the Flipper `.sub` files.
- `test/model_rx.py`: channel + the integer demodulator the C transcribes; run
  it after any change to the demodulator (a few minutes).
