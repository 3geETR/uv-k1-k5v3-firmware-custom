# Sokoban 1.0

A classic push-box puzzle overlay for F4HWN Labs ABI 1 / API 2.
Twenty-four original, deterministic levels fit a 10x6 board of 8x8-pixel tiles;
the entire board is visible. No radio reception or transmission is needed.

Push every box onto a goal. Boxes cannot be pulled and two boxes cannot be
pushed together. A filled box marks one on a goal; an empty goal is a small dot.
The status bar shows the current level and battery. The sidebar shows boxes
on goals / total boxes, moves and pushes.

| Key | Action |
| --- | --- |
| 2 / 4 / 6 / 8 | Up / left / right / down; hold to repeat |
| * | Undo one action, including a push; the last 64 actions are retained |
| 0, then 0 again within two seconds | Restart the current level |
| 3 / 9 | Previous / next level, wrapping at the ends |
| MENU after winning | Start the next level |
| EXIT / PTT | Exit; PTT does not transmit |

Undo also works after winning. Changing levels or restarting clears undo.
The current level is saved on exit through the resident deferred configuration
service. The board position and counters are not saved. No flash writes occur
while the overlay is running. The speaker is muted during the game; the loader
restores the radio when the app returns.

## Build and tests

```sh
./compile-app.sh sokoban
App/apps/sokoban/tests/run.sh
```

Output: `build/Apps/Sokoban.app`. Overlay code/data/BSS: 2416 B of 4096 B;
read-only assets: 720 B of 3840 B. Assets contain only the 24 packed levels.
No resident firmware or API changes are required.

`levels.py` constructs the original puzzles from solved boards by reversing
legal pushes. Its retained reverse paths provide solutions. Developer tests run
all 24 solutions through the actual C game engine and verify undo/redo of the
last 64 moves. ASan/UBSan tests also cover wall/box blocking, board edges, goals,
undo overflow, input repeat, win/undo/next-level transitions, restart
confirmation/cancellation/timeout, screensaver wake, held entry keys, UI bounds,
configuration staging/wrapping/invalid values, exit cleanup and asset errors.

The first level is a two-step introduction; later levels use two or three
boxes. Levels are regenerated deterministically with no network access.
