# CW USB host tests

Generate assets with the normal CW USB build, then run `python
App/apps/cwusb/test/arming.py` from the repository root. Python 3 and a C11
compiler are required (`HOST_CC`, default `gcc`). Results and generated host
sources are placed in ignored `test/out/`. The test compiles the actual app
source, replacing MMIO, IRQ operations and API callbacks for deterministic
simulation. ARM builds separately verify the real API layout and memory limit.
