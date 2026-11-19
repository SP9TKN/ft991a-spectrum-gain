"""Buduje MAIN test_11: test_10 z czasem trybu C.S ok. 1 s zamiast ok. 3 s. NIC NIE WGRYWA."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_test as b
import build_test08 as b8
import build_test10 as b10

b8.TICKS = 100
b10.OUT = b.ROOT / 'test_11'

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    b10.OUT.mkdir(exist_ok=True)
    b10.build_main()
