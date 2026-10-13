#!/usr/bin/env python3
"""Pure-Python model of the POCSAG receive chain, and the integer demodulator
the radio app runs (written to be transliterated to C: ints, shifts, no
division). Keep pocsagrx_app.c in step with class Demod and class Slicer.

Chain: NRZ bits -> discriminator output in Hz (+/- deviation) + offset + white
noise -> radio audio path, RAW (filters off): a high-pass whose corner is NOT
known on the BK4829 (hp_hz, the parameter this model exists for) and the
measured 3.3 kHz wall -> 12-bit ADC on PA4 around 2048 at 9.6 kHz (optional
clock error) -> Demod -> pages.

The high-pass is the difficulty: POCSAG has runs of 13 equal bits (11 ms) and a
high-passed NRZ level droops back to zero; with a high corner only a pulse is
left at each change of level. Demod (per ADC sample):
  DC removal -> 4-sample box (half a bit) -> y
  five slicers of two kinds, for the corner is not known:
  - quantized feedback ("q", k): the high-pass removed the low-passed signal,
    so it is put back from the decided level: r = y + fb,
    fb += (A * sign(r) - fb) >> k, with A the mean of |r|. Best in noise, for
    corners up to ~300 Hz. k = None is the plain slicer.
  - hysteresis ("s", n): the level flips when y passes +/- n/8 of its peak and
    holds in between, whether y droops or not. Holds from 10 Hz to ~1.5 kHz.
  Each slicer: DPLL on the changes of its level, a bit at mid-bit, the last 32
  bits compared with the sync codeword and its complement (either polarity),
  then 16 codewords per batch: BCH check, one wrong bit corrected, pages
  assembled as test/pocsag.py Decoder does.

  model_rx.py            runs the test sweep, prints a table
"""
import math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pocsag
from flipper_pocsag import test_bits

FS_SIM = 96000
FS_ADC = 9600
BIAS = 2048
LSB_PER_HZ = 0.065      # measured on the K1 (EPIRB 406 lab): ~2.3 kHz -> ~150 LSB
FLIPPER_DEV = 2380.0
PAGER_DEV = 4500.0
SYNC_ERR = 2            # wrong bits tolerated in a sync codeword


# ---------------------------------------------------------------- channel ----

def nrz_wave(bits, dev=FLIPPER_DEV, baud=1200):
    """Discriminator output (Hz): a 1 on the lower frequency, 100 ms of carrier
    first (sent as zeros, as the Flipper file does)."""
    spb = FS_SIM / baud
    lead = [dev] * int(0.1 * FS_SIM)
    return lead + [(-dev if bits[int(i / spb)] else dev) for i in range(int(len(bits) * spb))]


def biquad_lp(x, fc):
    w = math.tan(math.pi * fc / FS_SIM)
    q = 1 / math.sqrt(2)
    n = 1 / (1 + w / q + w * w)
    b0 = w * w * n; b1 = 2 * b0; a1 = 2 * (w * w - 1) * n; a2 = (1 - w / q + w * w) * n
    y, x1, x2, y1, y2 = [], 0.0, 0.0, 0.0, 0.0
    for v in x:
        o = b0 * v + b1 * x1 + b0 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, o
        y.append(o)
    return y


def rc_hp(x, fc):
    a = math.exp(-2 * math.pi * fc / FS_SIM)
    y, acc, prev = [], 0.0, 0.0
    for v in x:
        acc = a * (acc + v - prev)
        prev = v
        y.append(acc)
    return y


def channel(sig, hp_hz=30.0, noise_hz=0.0, off_hz=0.0, ppm=0.0, seed=1, gap_ms=150):
    rnd = random.Random(seed)
    gap = int(gap_ms * 1e-3 * FS_SIM)
    # no carrier around the burst: the discriminator outputs full-scale noise
    x = [rnd.gauss(0, 6000) for _ in range(gap)]
    x += [v + off_hz + rnd.gauss(0, noise_hz) for v in sig]
    x += [rnd.gauss(0, 6000) for _ in range(gap)]
    x = rc_hp(biquad_lp(biquad_lp(x, 3300), 3300), hp_hz)
    step = FS_SIM / FS_ADC * (1 + ppm * 1e-6)
    out, p = [], 0.0
    while p < len(x) - 1:
        i = int(p); f = p - i
        v = x[i] * (1 - f) + x[i + 1] * f
        out.append(min(4095, max(0, int(round(BIAS + LSB_PER_HZ * v + rnd.gauss(0, 1))))))
        p += step
    return out


# ------------------------------------------------------ integer demodulator --

def syndrome(cw):
    r = cw >> 1
    for i in range(30, 9, -1):
        if r & (1 << i):
            r ^= pocsag.GEN << (i - 10)
    return r


def ones(v):
    n = 0
    while v:
        v &= v - 1
        n += 1
    return n


def fix(cw):
    """The codeword, one wrong bit corrected, or -1. The syndrome of a single
    wrong bit i (1..31) is x^(i-1) modulo the generator: the powers of x are
    walked until one matches. The parity then tells a second wrong bit, or,
    with a null syndrome, that the parity bit itself is the wrong one."""
    global fixed
    fixed = False
    s = syndrome(cw)
    if s:
        fixed = True
        t, i = 1, 1
        while t != s:
            t <<= 1
            if t & 0x400:
                t ^= pocsag.GEN
            i += 1
            if i > 31:
                return -1
        cw ^= 1 << i
    if ones(cw) & 1:
        if s:
            return -1
        fixed = True
        cw ^= 1
    return cw


fixed = False           # fix() corrected a bit in the last codeword it returned
DIRTY_WORDS = 8         # codewords a slicer is not trusted to correct after a bad one


class Slicer:
    """One slicer, ("q", k) or ("s", n), with its own DPLL and batch decoder."""
    def __init__(self, dm, spec):
        self.dm = dm
        self.kind, self.k = spec
        self.fb = 0; self.amp = 0          # q: restored baseline, mean |r| (both Q4); s: amp = peak of |y|
        self.rprev = 0; self.phase = 0
        self.sr = 0                        # the last 32 bits, the newest in bit 0
        self.inv = 0                       # polarity found at the sync codeword
        self.nb = 0                        # bits of the codeword being read; 0 with word < 0: hunting
        self.word = -1                     # codeword of the batch being read, 16 = the next sync
        self.dirty = 0                     # codewords left before a correction is trusted again
        self.ric = -1; self.func = 0       # page being received (-1: none)
        self.acc = 0; self.na = 0; self.text = []

    def step(self, y):
        dm = self.dm
        if self.kind == "s":
            a = y if y >= 0 else -y
            if a > self.amp:
                self.amp += (a - self.amp) >> 2
            else:
                self.amp -= self.amp >> 10
            t = (self.amp * self.k) >> 3
            r = self.rprev                     # the level holds between the thresholds
            if y > t:
                r = 1
            elif y < -t:
                r = -1
        else:
            r = (y << 4) + self.fb
            if self.k is not None:
                a = r if r >= 0 else -r
                self.amp += (a - self.amp) >> 6
                self.fb += ((self.amp if r >= 0 else -self.amp) - self.fb) >> self.k
        self.phase += dm.step
        if (r > 0) != (self.rprev > 0):
            self.phase += (dm.ctr - self.phase) >> dm.pll
        self.rprev = r
        if self.phase >= 65536:
            self.phase -= 65536
            self.bit(0 if r > 0 else 1)        # the lower frequency is a 1

    def bit(self, b):
        self.sr = ((self.sr << 1) | b) & 0xFFFFFFFF
        if self.word < 0:
            e = ones(self.sr ^ pocsag.SYNC)
            if e <= SYNC_ERR or e >= 32 - SYNC_ERR:
                self.inv = 0xFFFFFFFF if e > 16 else 0
                self.word = 0
                self.nb = 0
            return
        self.nb += 1
        if self.nb < 32:
            return
        self.nb = 0
        cw = self.sr ^ self.inv
        if self.word == pocsag.BATCH_WORDS:            # the next batch's sync, or the end
            if ones(cw ^ pocsag.SYNC) <= SYNC_ERR:
                self.word = 0
            else:
                self.close()
                self.word = -1
            return
        # A word with 3 wrong bits or more "corrects" into another codeword
        # once in 60: a slicer that just read a bad word is reading garbage,
        # and only its error-free codewords are taken for a while.
        cw = fix(cw)
        if cw < 0:
            self.dirty = DIRTY_WORDS
        elif self.dirty:
            self.dirty -= 1
            if fixed:
                cw = -1
        self.codeword(cw)
        self.word += 1

    def codeword(self, cw):
        # The all-zero word is a valid codeword (address 0, function 0): it is
        # what a slicer stuck on one level reads, so it is refused as a bad one.
        if cw <= 0 or cw == pocsag.IDLE:
            self.close()
        elif cw >> 31:
            if self.ric >= 0:
                n = 4 if self.func == pocsag.FUNC_NUMERIC else 7
                for i in range(30, 10, -1):
                    self.acc |= ((cw >> i) & 1) << self.na
                    self.na += 1
                    if self.na == n:
                        ch = ord(pocsag.NUMERIC[self.acc]) if n == 4 else self.acc
                        if 32 <= ch < 127 and len(self.text) < self.dm.TEXT_MAX:
                            self.text.append(ch)
                        self.acc = self.na = 0
        else:
            self.close()
            self.at = self.dm.n
            self.ric = ((cw >> 13) & 0x3FFFF) << 3 | (self.word >> 1)
            self.func = (cw >> 11) & 3
            self.acc = self.na = 0
            self.text = []

    def close(self):
        if self.ric >= 0:
            t = bytes(self.text).decode()
            if self.func == pocsag.FUNC_NUMERIC:
                t = t.rstrip(" ")
            # An address alone is dropped: a slicer that slipped a bit reads
            # shifted codewords, which are valid ones as often as not (the
            # code is cyclic), and they come out as addresses without text.
            if t:
                self.dm.found((self.ric, self.func, t), self.at)
        self.ric = -1


class Demod:
    TEXT_MAX = 80

    DUP_SAMPLES = 128              # address codewords this close (half a codeword of
                                   # 256 samples): the same page from another slicer

    SLICERS = (("q", 5), ("q", 4), ("s", 1), ("s", 2), ("s", 4))

    def __init__(self, fs=FS_ADC, pll=3, ctr=36864, ks=SLICERS):
        self.pll, self.ctr = pll, ctr
        self.dc = BIAS << 4
        self.box = [0, 0, 0, 0]; self.bi = 0; self.sum = 0
        self.step = (65536 * 1200 + fs // 2) // fs
        self.sl = [Slicer(self, k) for k in ks]
        self.pages = []; self.when = []            # pages, the sample the address of each came at
        self.n = 0                                 # sample count

    def found(self, page, at):
        # The five slicers read the same transmission: each gives the same
        # page, and one that lost a codeword gives it cut short. What tells the
        # same page from another one is not its text (two pages may share
        # theirs, or its beginning) but where it sits: its address codeword
        # came at the same sample, within half a codeword, for every slicer,
        # and two pages are a codeword apart at least. The longest copy is kept.
        for j in range(len(self.pages) - 1, -1, -1):
            old = self.pages[j]
            if old[:2] != page[:2] or abs(at - self.when[j]) >= self.DUP_SAMPLES:
                continue
            if len(page[2]) > len(old[2]):
                self.pages[j] = page
            return
        self.pages.append(page)
        self.when.append(at)

    def skip(self, n):
        """n samples were not taken (keys, screen): the bit clocks run on and the
        missing bits are read as zeros, so the codeword alignment is kept."""
        for _ in range(n):
            self.n += 1
            for s in self.sl:
                s.phase += self.step
                if s.phase >= 65536:
                    s.phase -= 65536
                    s.bit(0)

    def sample(self, adc):
        self.n += 1
        self.dc += ((adc << 4) - self.dc) >> 8
        x = adc - (self.dc >> 4)
        self.sum += x - self.box[self.bi]
        self.box[self.bi] = x
        self.bi = (self.bi + 1) & 3
        for s in self.sl:
            s.step(self.sum)


def run(adc, hole=None, **kw):
    """hole = (first sample, samples): a stretch not sampled, as when the app
    serves the keys and the screen."""
    d = Demod(**kw)
    for i, s in enumerate(adc):
        if hole and hole[0] <= i < hole[0] + hole[1]:
            if i == hole[0]:
                d.skip(hole[1])
            continue
        d.sample(s)
    for s in d.sl:
        s.close()
    return d.pages


# ------------------------------------------------------------------ sweep ----

def main():
    tb = test_bits()
    sl = Demod.SLICERS
    print("high-pass corner of the audio path: each slicer alone, then the five together")
    print("%-8s %5s %6s | %s | %s" % ("page", "hp", "noise", " ".join("%s%d " % k for k in sl), "all"))
    bad = 0
    for name in ("alpha", "long", "inverted", "biterr"):
        for hp in (10, 30, 100, 300, 600, 1000, 1500):
            for noise in (0, 1500):
                b, want = tb[name]
                adc = channel(nrz_wave(b), hp, noise)
                res = " ".join("ok " if run(adc, ks=(k,)) == want else "-  " for k in sl)
                got = run(adc)
                bad += got != want
                print("%-8s %5d %6d | %s | %s" % (name, hp, noise, res, "ok" if got == want else "FAIL %r" % (got,)))
    print("other cases, the five slicers, 3 noise seeds")
    for name, hp, noise, off, ppm, dev in (
            ("two", 30, 1500, 0, 0, FLIPPER_DEV), ("numeric", 1000, 1500, 0, 0, FLIPPER_DEV),
            ("same", 30, 1500, 0, 0, FLIPPER_DEV), ("same", 1000, 1500, 0, 0, FLIPPER_DEV),
            ("alpha", 30, 1500, 4000, 0, FLIPPER_DEV), ("alpha", 1000, 1500, -4000, 0, FLIPPER_DEV),
            ("long", 30, 1500, 0, 10000, FLIPPER_DEV), ("long", 1000, 1500, 0, -10000, FLIPPER_DEV),
            ("long", 100, 3000, 0, 0, FLIPPER_DEV), ("long", 100, 3000, 0, 0, PAGER_DEV),
            ("long", 1000, 3000, 0, 0, PAGER_DEV)):
        b, want = tb[name]
        got = [run(channel(nrz_wave(b, dev), hp, noise, off, ppm, s)) for s in (1, 2, 3)]
        ok = sum(g == want for g in got)
        print("%-8s hp %4d noise %4d off %5d ppm %6d dev %4d | %d/3%s" %
              (name, hp, noise, off, ppm, dev, ok, "" if ok == 3 else "  " + repr([g for g in got if g != want][0])))
    # a 13 ms hole (keys and screen) in the second batch: the alignment holds,
    # the page being received is cut there
    b, want = tb["two"]
    adc = channel(nrz_wave(b), 30, 0)
    print("hole of 130 samples in batch 2 ->", run(adc, hole=(int((0.25 + 0.48 + 0.45 + 0.1) * FS_ADC), 130)))
    rnd = random.Random(7)
    noise = [rnd.gauss(0, 6000) for _ in range(60 * FS_SIM)]
    for hp in (30, 1000):
        x = rc_hp(biquad_lp(biquad_lp(noise, 3300), 3300), hp)
        adc = [min(4095, max(0, int(round(BIAS + LSB_PER_HZ * x[i * 10])))) for i in range(len(x) // 10)]
        print("noise 60 s, hp %d ->" % hp, run(adc) or "nothing")
    print("wrong results in the corner table: %d" % bad)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--one":
        print(run(channel(nrz_wave(test_bits()["alpha"][0]))))
    else:
        main()
