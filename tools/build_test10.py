"""Buduje test_10: MAIN = test_08 + stan trybu C.S w bajcie 17 bloku 0x21, TFT = test_03 + liczba tylko przy aktywnym trybie. NIC NIE WGRYWA."""
import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_test as b
import build_test08 as b8
import build_test09 as b9

OUT = b.ROOT / 'test_10'
TX_SITE = 0x2F936
ACTIVE = 0x0C31CFDA        # bajt 17 kopii bloku 0x21 w TFT


def add_tx(img, top, h):
    c = b8.COUNTER.to_bytes(4, 'big')
    code = (b'\x6a\x28' + b.CELL.to_bytes(4, 'big') + bytes.fromhex('01736ca8')   # bajt 16: gain
            + b'\x6b\x20' + c + b'\x79\x20\x00\x00'                               # licznik trybu
            + b'\x47\x04' + b'\xf8\x01' + b'\x40\x02' + b'\xf8\x00'               # 1 = aktywny, 0 = nie
            + bytes.fromhex('01736ca8')                                           # bajt 17: stan
            + bytes.fromhex('0b72 5470'))                                         # pomin bajt 18, rts
    img[top:top + len(code)] = code
    b.patch(img, TX_SITE, b.j24(0x5A, h['TX']), b.j24(0x5A, top))
    return top + len(code), top


def build_main():
    raw = b.SFL_IN.read_bytes()
    img, top0 = b.image_from(raw)
    assert top0 == b.OLD_TOP
    assert b.rebuild(raw, img, top0) == raw
    top, h, _ = b.build_main(img)
    top2, *_ = b8.add_stubs(img, top, h)
    top3, tx = add_tx(img, top2, h)
    assert top3 < 0x40000
    sfl, s = b.set_checksum(b.rebuild(raw, img, top3), img)
    (OUT / 'AH067_V0207.SFL').write_bytes(sfl)
    print('MAIN koniec', hex(top3), 'TX', hex(tx), 'suma %08X dolna %08X' % (s, (s + 0x01FE0000) & 0xFFFFFFFF), 'plik', len(sfl))


def stub(font_addr):
    a = b9.Asm(b9.STUB)
    BT, BF = 0x89, 0x8B
    a.w(0x4F22)                            # sts.l pr,@-r15
    a.lit(3, b9.ORIG)
    a.w(0x434B)                            # jsr/n @r3
    a.lit(1, ACTIVE)
    a.w(0x6110, 0x2118)                    # mov.b @r1,r1; tst r1,r1
    a.br(BT, 'out')
    a.lit(2, b9.COL29)
    a.w(0x6322)                            # mov.l @r2,r3
    a.lit(6, b9.X0)
    a.w(0x3363)                            # cmp/ge r6,r3
    a.br(BF, 'out')
    a.w(0x7628, 0x3637)                    # add #40,r6; cmp/gt r3,r6
    a.br(BF, 'out')
    a.lit(1, b9.GAIN)
    a.w(0x6110, 0x4111)                    # mov.b @r1,r1; cmp/pz r1
    a.w(0xE300 | b9.BLANK)
    a.br(BT, 'nn')
    a.w(0x611B, 0xE300 | b9.MINUS)         # neg r1,r1; mov #minus,r3
    a.label('nn')
    a.lit(4, b9.GAIN)
    a.w(0x6440, 0x4415)                    # mov.b @r4,r4; cmp/pl r4
    a.br(BF, 'np')
    a.w(0xE300 | b9.PLUS)
    a.label('np')
    a.w(0xE414, 0x3147)                    # mov #20,r4; cmp/gt r4,r1
    a.br(BT, 'out')
    a.w(0xE400 | b9.BLANK, 0xE50A, 0x3153)
    a.br(BF, 'one')
    a.w(0xE401, 0x71F6, 0x3153)
    a.br(BF, 'two')
    a.w(0xE402, 0x71F6)
    a.label('two')
    a.lit(2, b9.STATE + 4)
    a.w(0x2230, 0x7201, 0x2240, 0x7201, 0x2210)
    a.w(0xE000, 0x2008)                    # T = 1
    a.br(BT, 'paint0')
    a.label('one')
    a.lit(2, b9.STATE + 4)
    a.w(0xE400 | b9.BLANK)
    a.w(0x2240, 0x7201, 0x2230, 0x7201, 0x2210)
    a.label('paint0')
    a.lit(1, b9.BUF29 + b9.Y0 * b9.STRIDE + b9.X0 * 2)
    a.bsr('paint')
    a.lit(1, b9.BUF59 + b9.Y0 * b9.STRIDE + b9.X0 * 2)
    a.bsr('paint')
    a.label('out')
    a.w(0x4F26, 0x006B)                    # lds.l @r15+,pr; rts/n
    a.label('paint')
    a.w(0xE200)
    a.label('row')
    a.w(0x6613, 0xE300)
    a.label('char')
    a.lit(0, b9.STATE + 4)
    a.w(0x303C, 0x6000)
    a.w(0x6403, 0x4408, 0x4400, 0x3408)
    a.w(0x6023, 0x4001, 0x340C)
    a.lit(0, font_addr)
    a.w(0x044C, 0xE505)
    a.label('bit')
    a.w(0xE010, 0x2408, 0xE700)
    a.br(BT, 'z')
    a.w(0xE7FF)
    a.label('z')
    a.w(0x2671, 0x7602, 0x2671, 0x7602)
    a.w(0x4400, 0x75FF, 0x2558)
    a.br(BF, 'bit')
    a.w(0xE700, 0x2671, 0x7602, 0x2671, 0x7602)
    a.w(0x7301, 0xE003, 0x3303)
    a.br(BF, 'char')
    a.lit(0, b9.STRIDE)
    a.w(0x310C, 0x7201, 0xE00E, 0x3203)
    a.br(BF, 'row')
    a.w(0x006B)
    return a.assemble()


def build_tft():
    d = bytearray(b9.IN.read_bytes())
    assert hashlib.sha256(d).hexdigest() == b9.IN_SHA
    font = bytes(x for g in b9.FONT for x in g)
    fa = b9.STUB + len(stub(0))
    code = stub(fa)
    blob = code + font
    o = b9.STUB - b9.BASE
    assert b9.STUB + len(blob) <= b9.STATE
    assert d[o:b9.STATE + 8 - b9.BASE] == b'\0' * (b9.STATE + 8 - b9.STUB)
    d[o:o + len(blob)] = blob
    lo = b9.HOOK_LIT - b9.BASE
    assert struct.unpack('>I', d[lo:lo + 4])[0] == b9.ORIG
    d[lo:lo + 4] = struct.pack('>I', b9.STUB)
    (OUT / 'TFT_AH067M_V02-00.bin').write_bytes(d)
    print('TFT blok', len(blob), 'SHA', hashlib.sha256(d).hexdigest())


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(exist_ok=True)
    build_main()
    build_tft()
