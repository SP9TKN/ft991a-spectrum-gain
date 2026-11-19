"""Buduje TFT test_09: test_03 + wartosc SPECTRUM GAIN w rogu widma po kazdej zmianie. NIC NIE WGRYWA."""
import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / 'work'   # ft991a_patch.py sets the real paths
IN = ROOT / 'test_03/TFT_AH067M_V02-00.bin'
IN_SHA = 'ac0ecd12b6fd74ac23c7c158018e636b9f7304320b0d3df79908ec466c3054bd'
OUT = ROOT / 'test_09/TFT_AH067M_V02-00.bin'
BASE = 0x0C000000
HOOK_LIT = 0x0C0034E4      # jedyne wywolanie obslugi probki widma
ORIG = 0x0C0159E0
STUB = 0x0C001CA0
GAIN = 0x0C31CFD9          # bajt 16 kopii bloku 0x21
COL29 = 0x0C31CE74         # kolumna rysowania widma 29
BUF29 = 0x0C318A76
BUF59 = 0x0C374888
STRIDE = 598
X0, Y0 = 258, 1            # prostokat 36 x 14 pikseli
SWEEPS = 30                # liczba przebiegow, przez ktore widac liczbe
STATE = 0x0C001FE0         # poprzedni gain (1), licznik (2 od +2), znaki (3 od +4)
FONT = [
    [14, 17, 19, 21, 25, 17, 14], [4, 12, 4, 4, 4, 4, 14], [14, 17, 1, 2, 4, 8, 31], [31, 2, 4, 2, 1, 17, 14],
    [2, 6, 10, 18, 31, 2, 2], [31, 16, 30, 1, 1, 17, 14], [6, 8, 16, 30, 17, 17, 14], [31, 1, 2, 4, 8, 8, 8],
    [14, 17, 17, 14, 17, 17, 14], [14, 17, 17, 15, 1, 2, 12],
    [0, 4, 4, 31, 4, 4, 0], [0, 0, 0, 31, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0],
]
PLUS, MINUS, BLANK = 10, 11, 12


class Asm:
    def __init__(self, base):
        self.base, self.items, self.labels, self.pool = base, [], {}, {}

    def label(self, n):
        self.labels[n] = len(self.items)

    def w(self, *vals):
        self.items += list(vals)

    def br(self, op, target):       # 0x89 bt, 0x8B bf
        self.items.append(('b', op, target))

    def bsr(self, target):
        self.items += [('s', target), 0x0009]

    def lit(self, reg, value):
        self.items.append(('l', reg, value))

    def assemble(self):
        n = len(self.items)
        pool_at = self.base + n * 2
        if pool_at % 4:
            self.items.append(0x0009)
            n += 1
            pool_at += 2
        vals = []
        for it in self.items:
            if isinstance(it, tuple) and it[0] == 'l' and it[2] not in vals:
                vals.append(it[2])
        out = []
        for i, it in enumerate(self.items):
            pc = self.base + i * 2
            if isinstance(it, int):
                out.append(it)
            elif it[0] == 'b':
                d = (self.labels[it[2]] - i - 2)
                assert -128 <= d < 128
                out.append((it[1] << 8) | (d & 255))
            elif it[0] == 's':
                d = (self.labels[it[1]] - i - 2)
                assert -2048 <= d < 2048
                out.append(0xB000 | (d & 0xFFF))
            else:
                a = pool_at + vals.index(it[2]) * 4
                d = a - ((pc & ~3) + 4)
                assert 0 <= d and d % 4 == 0 and d // 4 < 256
                out.append(0xD000 | (it[1] << 8) | (d // 4))
        return struct.pack('>%dH' % len(out), *out) + b''.join(struct.pack('>I', v) for v in vals)


def stub(font_addr):
    a = Asm(STUB)
    BT, BF = 0x89, 0x8B
    a.w(0x4F22, 0x7FFC, 0x2F52)            # sts.l pr,@-r15; add #-4,r15; mov.l r5,@r15
    a.lit(3, ORIG)
    a.w(0x434B, 0x65F2, 0x7F04)            # jsr/n @r3; mov.l @r15,r5; add #4,r15
    a.lit(1, GAIN)
    a.w(0x6110)                            # mov.b @r1,r1
    a.lit(2, STATE)
    a.w(0x6320, 0x3310)                    # mov.b @r2,r3; cmp/eq r1,r3
    a.br(BT, 'same')
    a.w(0x2210)                            # mov.b r1,@r2
    a.w(0xE300 | SWEEPS)                   # mov #N,r3
    a.lit(4, STATE + 2)
    a.w(0x2431)                            # mov.w r3,@r4
    a.label('same')
    a.lit(4, STATE + 2)
    a.w(0x6341, 0x633D, 0x2338)            # mov.w @r4,r3; extu.w r3,r3; tst r3,r3
    a.br(BT, 'out')
    a.w(0x2558)                            # tst r5,r5
    a.br(BF, 'notick')
    a.w(0x73FF, 0x2431)                    # add #-1,r3; mov.w r3,@r4
    a.label('notick')
    a.lit(2, COL29)
    a.w(0x6322)                            # mov.l @r2,r3
    a.lit(6, X0)
    a.w(0x3363)                            # cmp/ge r6,r3
    a.br(BF, 'out')
    a.w(0x7628, 0x3637)                    # add #40,r6; cmp/gt r3,r6
    a.br(BF, 'out')
    # znaki
    a.w(0x4111)                            # cmp/pz r1 (r1 = gain)
    a.w(0xE300 | BLANK)                    # mov #blank,r3
    a.br(BT, 'nn')
    a.w(0x611B, 0xE300 | MINUS)            # neg r1,r1; mov #minus,r3
    a.label('nn')
    a.lit(4, 0x0C31CFD9)
    a.w(0x6440, 0x4415)                    # mov.b @r4,r4; cmp/pl r4
    a.br(BF, 'np')
    a.w(0xE300 | PLUS)
    a.label('np')
    a.w(0xE414, 0x3147)                    # mov #20,r4; cmp/gt r4,r1
    a.br(BT, 'out')
    a.w(0xE400 | BLANK, 0xE50A, 0x3153)    # mov #blank,r4; mov #10,r5; cmp/ge r5,r1
    a.br(BF, 'one')
    a.w(0xE401, 0x71F6, 0x3153)            # mov #1,r4; add #-10,r1; cmp/ge r5,r1
    a.br(BF, 'two')
    a.w(0xE402, 0x71F6)                    # mov #2,r4; add #-10,r1
    a.label('two')
    a.lit(2, STATE + 4)
    a.w(0x2230)                            # mov.b r3,@r2       znak na pozycji 0
    a.w(0x7201, 0x2240)                    # add #1,r2; mov.b r4,@r2
    a.w(0x7201, 0x2210)                    # add #1,r2; mov.b r1,@r2
    a.w(0xE000, 0x2008)                    # mov #0,r0; tst r0,r0, czyli T = 1
    a.br(BT, 'paint0')
    a.label('one')
    a.lit(2, STATE + 4)
    a.w(0xE400 | BLANK)                    # mov #blank,r4
    a.w(0x2240, 0x7201, 0x2230, 0x7201, 0x2210)   # blank, znak, jednosci
    a.label('paint0')
    a.lit(1, BUF29 + Y0 * STRIDE + X0 * 2)
    a.bsr('paint')
    a.lit(1, BUF59 + Y0 * STRIDE + X0 * 2)
    a.bsr('paint')
    a.label('out')
    a.w(0x4F26, 0x006B)                    # lds.l @r15+,pr; rts/n
    # malowanie prostokata; r1 = adres pierwszego piksela
    a.label('paint')
    a.w(0xE200)                            # mov #0,r2
    a.label('row')
    a.w(0x6613, 0xE300)                    # mov r1,r6; mov #0,r3
    a.label('char')
    a.lit(0, STATE + 4)
    a.w(0x303C, 0x6000)                    # add r3,r0; mov.b @r0,r0
    a.w(0x6403, 0x4408, 0x4400, 0x3408)    # mov r0,r4; shll2 r4; shll r4; sub r0,r4 (r4 = 7g)
    a.w(0x6023, 0x4001, 0x340C)            # mov r2,r0; shlr r0; add r0,r4
    a.lit(0, font_addr)
    a.w(0x044C, 0xE505)                    # mov.b @(r0,r4),r4; mov #5,r5
    a.label('bit')
    a.w(0xE010, 0x2408, 0xE700)            # mov #16,r0; tst r0,r4; mov #0,r7
    a.br(BT, 'z')
    a.w(0xE7FF)                            # mov #-1,r7
    a.label('z')
    a.w(0x2671, 0x7602, 0x2671, 0x7602)    # 2 piksele
    a.w(0x4400, 0x75FF, 0x2558)            # shll r4; add #-1,r5; tst r5,r5
    a.br(BF, 'bit')
    a.w(0xE700, 0x2671, 0x7602, 0x2671, 0x7602)   # 2 piksele tla
    a.w(0x7301, 0xE003, 0x3303)            # add #1,r3; mov #3,r0; cmp/ge r0,r3
    a.br(BF, 'char')
    a.lit(0, STRIDE)
    a.w(0x310C, 0x7201, 0xE00E, 0x3203)    # add r0,r1; add #1,r2; mov #14,r0; cmp/ge r0,r2
    a.br(BF, 'row')
    a.w(0x006B)                            # rts/n
    return a.assemble()


def main():
    d = bytearray(IN.read_bytes())
    assert hashlib.sha256(d).hexdigest() == IN_SHA
    font = bytes(b for g in FONT for b in g)
    code = stub(0)                         # rozmiar
    font_addr = STUB + len(code)
    code = stub(font_addr)
    assert len(stub(font_addr)) == len(code)
    blob = code + font
    o = STUB - BASE
    assert STUB + len(blob) <= STATE
    assert d[o:STATE + 8 - BASE] == b'\0' * (STATE + 8 - STUB)
    d[o:o + len(blob)] = blob
    lo = HOOK_LIT - BASE
    assert struct.unpack('>I', d[lo:lo + 4])[0] == ORIG
    d[lo:lo + 4] = struct.pack('>I', STUB)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes(d)
    print('zapisano', OUT, 'blok', len(blob), hex(font_addr), hashlib.sha256(d).hexdigest())


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
