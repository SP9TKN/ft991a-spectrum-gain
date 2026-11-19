"""Buduje MAIN test_08: C.S krotkie = menu, dlugie = gain na MULTI, koniec 3 s po ostatnim obrocie. NIC NIE WGRYWA."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_test as b

OUT = b.ROOT / 'test_08'
COUNTER = 0xFF204A         # slowo bez odwolan, czyszczone przy starcie; 0 = tryb wylaczony
LONG = 0xFF2049            # bit 0: C.S wywolane z dlugiego nacisniecia
TICKS = 300                # 300 x 10 jednostek harmonogramu
CS_ENTRY = 0xB0C2          # oryginalna procedura C.S
EMPTY = 0x15442            # samo rts
T0_CS = 0x1576E            # nacisniecie
T1_CS = 0x15A7A            # krotkie puszczenie
T2_CS = 0x15D86            # dlugie nacisniecie
CS_SITE = 0xB18A           # C.S poza menu: mov.b @0xffb319,r0l
CS_NEXT = 0xB190
BEEP2 = 0x493C             # fabryczny podwojny pisk, konczy sie rts
ROT_SITE = 0x1405E
ROT_OLD = 0x14212
TICK_SITE = 0x32422
FRAM_WRITE = 0x9594
CELL_FRAM = 0x0274


def add_stubs(img, top, h):
    c = COUNTER.to_bytes(4, 'big')
    lg = LONG.to_bytes(4, 'big')
    cell = b.CELL.to_bytes(4, 'big')
    t = TICKS.to_bytes(2, 'big')
    rd = b'\x6b\x20' + c
    wr = b'\x6b\xa0' + c
    tst = b'\x79\x20\x00\x00'
    orig = bytes.fromhex('6a28 00ffb319')

    p_long = top
    code = (bytes.fromhex('6a30 00ff201d 7360') + b'\x46\x14'      # menu otwarte: skok na rts
            + b'\x6a\x38' + lg + b'\x70\x00'
            + b.j24(0x5E, CS_ENTRY)
            + b'\x6a\x38' + lg + b'\x72\x00'
            + b'\x54\x70')
    p_cs = p_long + len(code)
    code += (b'\x6a\x30' + lg + b'\x73\x00' + b'\x46\x0a'
             + orig + b.j24(0x5A, CS_NEXT)
             + b'\x79\x00' + t + wr + b.j24(0x5A, BEEP2))
    p_rot = p_long + len(code)
    code += (rd + tst + b'\x46\x04' + b.j24(0x5A, ROT_OLD)
             + b'\x79\x00' + t + wr
             + bytes.fromhex('6a30 00ff2010 7320') + b'\x46\x06'
             + b.j24(0x5E, h['A']) + b'\x40\x04' + b.j24(0x5E, h['B'])
             + b'\x79\x02\x00\x01' + b'\x79\x01' + CELL_FRAM.to_bytes(2, 'big')
             + b'\x7a\x03' + cell + b.j24(0x5A, FRAM_WRITE))
    p_tick = p_long + len(code)
    code += (bytes.fromhex('6a38 00ff2007 7000') + rd + tst + b'\x47\x08' + b'\x1b\x50' + wr + b'\x54\x70')
    img[p_long:p_long + len(code)] = code

    e = lambda a: a.to_bytes(4, 'big')
    b.patch(img, T0_CS, e(CS_ENTRY), e(EMPTY))
    b.patch(img, T1_CS, e(EMPTY), e(CS_ENTRY))
    b.patch(img, T2_CS, e(EMPTY), e(p_long))
    b.patch(img, CS_SITE, orig, b.j24(0x5A, p_cs) + b'\x00\x00')
    b.patch(img, ROT_SITE, b.j24(0x5E, ROT_OLD), b.j24(0x5E, p_rot))
    b.patch(img, TICK_SITE, bytes.fromhex('6a38 00ff2007 7000'), b.j24(0x5A, p_tick) + b'\x00' * 4)
    return p_long + len(code), p_long, p_cs, p_rot, p_tick


def main():
    raw = b.SFL_IN.read_bytes()
    img, top0 = b.image_from(raw)
    assert top0 == b.OLD_TOP
    assert b.rebuild(raw, img, top0) == raw
    top, h, _ = b.build_main(img)
    top2, *pts = add_stubs(img, top, h)
    assert top2 < 0x40000
    sfl = b.rebuild(raw, img, top2)
    sfl, s = b.set_checksum(sfl, img)
    OUT.mkdir(exist_ok=True)
    (OUT / 'AH067_V0207.SFL').write_bytes(sfl)
    print('koniec', hex(top2), [hex(x) for x in pts], 'suma %08X' % s, 'dolna %08X' % ((s + 0x01FE0000) & 0xFFFFFFFF), 'plik', len(sfl))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
