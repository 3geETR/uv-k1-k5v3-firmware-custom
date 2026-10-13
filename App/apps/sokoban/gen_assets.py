#!/usr/bin/env python3
import os,sys
sys.dont_write_bytecode=True
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
from app_assets import Assets
from levels import levels
puzzles=levels();data=bytes(c[i]|(c[i+1]<<4) for c,_ in puzzles for i in range(0,60,2))
a=Assets('SOKOBAN');a.const('LEVEL_COUNT',len(puzzles));a.const('LEVEL_BYTES',30);a.u8('LEVELS',data);a.main()
