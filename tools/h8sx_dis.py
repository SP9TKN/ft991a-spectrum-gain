"""Minimalny dekoder H8/300H + czesc H8SX do czytania firmware MAIN FT-991A (tylko analiza)."""
import struct
import sys

RB = ['r%dh' % i for i in range(8)] + ['r%dl' % i for i in range(8)]
RW = ['r%d' % i for i in range(8)] + ['e%d' % i for i in range(8)]
RL = ['er%d' % i for i in range(8)]
CC = ['bra', 'brn', 'bhi', 'bls', 'bcc', 'bcs', 'bne', 'beq', 'bvc', 'bvs', 'bpl', 'bmi', 'bge', 'blt', 'bgt', 'ble']
IMM = ['mov', 'add', 'cmp', 'sub', 'or', 'xor', 'and']
RR8 = {0x08: 'add', 0x0C: 'mov', 0x14: 'or', 0x15: 'xor', 0x16: 'and', 0x18: 'sub', 0x1C: 'cmp', 0x0E: 'addx', 0x1E: 'subx'}
RR16 = {0x09: 'add', 0x0D: 'mov', 0x19: 'sub', 0x1D: 'cmp', 0x64: 'or', 0x65: 'xor', 0x66: 'and'}
IMM8 = {0x8: 'add', 0x9: 'addx', 0xA: 'cmp', 0xB: 'subx', 0xC: 'or', 0xD: 'xor', 0xE: 'and', 0xF: 'mov'}


def s8(x):
    return x - 256 if x & 0x80 else x


def s16(x):
    return x - 65536 if x & 0x8000 else x


def dec(d, a):
    """Zwraca (dlugosc, tekst) dla instrukcji pod adresem a."""
    b0, b1 = d[a], d[a + 1]
    hi, lo = b1 >> 4, b1 & 15

    def w(o):
        return struct.unpack('>H', d[a + o:a + o + 2])[0]

    def l(o):
        return struct.unpack('>I', d[a + o:a + o + 4])[0]

    if b0 == 0x00:
        return 2, 'nop' if b1 == 0 else '.word %02x%02x' % (b0, b1)
    if b0 == 0x01:
        n2 = d[a + 2]
        if b1 == 0x00:
            n3 = d[a + 3]
            h3, l3 = n3 >> 4, n3 & 15
            if n2 == 0x69:
                return 4, ('mov.l @er%d,er%d' % (h3, l3)) if h3 < 8 else ('mov.l er%d,@er%d' % (l3, h3 & 7))
            if n2 == 0x6D:
                return 4, ('mov.l @er%d+,er%d' % (h3, l3)) if h3 < 8 else ('mov.l er%d,@-er%d' % (l3, h3 & 7))
            if n2 == 0x6F:
                return 6, ('mov.l @(%d,er%d),er%d' % (s16(w(4)), h3, l3)) if h3 < 8 else ('mov.l er%d,@(%d,er%d)' % (l3, s16(w(4)), h3 & 7))
            if n2 == 0x6B:
                if h3 == 0:
                    return 6, 'mov.l @0x%04x:16,er%d' % (w(4), l3)
                if h3 == 2:
                    return 8, 'mov.l @0x%06x,er%d' % (l(4), l3)
                if h3 == 8:
                    return 6, 'mov.l er%d,@0x%04x:16' % (l3, w(4))
                if h3 == 0xA:
                    return 8, 'mov.l er%d,@0x%06x' % (l3, l(4))
            if n2 == 0x78:
                return 10, 'mov.l disp32 er%d %02x%02x %08x' % (h3 & 7, d[a + 4], d[a + 5], l(6))
        if b1 in (0x10, 0x20, 0x30):
            return 4, 'ldm/stm %02x %02x%02x' % (b1, n2, d[a + 3])
        if b1 in (0xC0, 0xD0):
            return 4, 'mulxs/divxs %02x %02x%02x' % (b1, n2, d[a + 3])
        if b1 == 0xF0:
            return 4, 'logic.l %02x %02x' % (n2, d[a + 3])
        if b1 == 0x40:
            return 4, 'ldc/stc %02x%02x' % (n2, d[a + 3])
        return 4, 'h8sx.%02x %02x%02x' % (b1, n2, d[a + 3])
    if b0 in RR8:
        return 2, '%s.b %s,%s' % (RR8[b0], RB[hi], RB[lo])
    if b0 in RR16:
        return 2, '%s.w %s,%s' % (RR16[b0], RW[hi], RW[lo])
    if b0 == 0x0A:
        if hi >= 8:
            return 2, 'add.l er%d,er%d' % (hi & 7, lo & 7)
        return 2, 'inc.b %s' % RB[lo]
    if b0 == 0x0B:
        return 2, {0: 'adds #1,er%d', 8: 'adds #2,er%d', 9: 'adds #4,er%d', 5: 'inc.w #1,r%d', 0xD: 'inc.w #2,r%d', 7: 'inc.l #1,er%d', 0xF: 'inc.l #2,er%d'}.get(hi, '.0b%x,%%d' % hi) % (lo & 7)
    if b0 == 0x0F:
        return 2, 'mov.l er%d,er%d' % (hi & 7, lo & 7) if hi >= 8 else 'daa %s' % RB[lo]
    if b0 == 0x1A:
        return 2, 'sub.l er%d,er%d' % (hi & 7, lo & 7) if hi >= 8 else 'dec.b %s' % RB[lo]
    if b0 == 0x1B:
        return 2, {0: 'subs #1,er%d', 8: 'subs #2,er%d', 9: 'subs #4,er%d', 5: 'dec.w #1,r%d', 0xD: 'dec.w #2,r%d', 7: 'dec.l #1,er%d', 0xF: 'dec.l #2,er%d'}.get(hi, '.1b%x,%%d' % hi) % (lo & 7)
    if b0 == 0x1F:
        return 2, 'cmp.l er%d,er%d' % (hi & 7, lo & 7) if hi >= 8 else 'das %s' % RB[lo]
    if b0 in (0x10, 0x11, 0x12, 0x13):
        name = {0x10: ['shll', 'shal'], 0x11: ['shlr', 'shar'], 0x12: ['rotxl', 'rotl'], 0x13: ['rotxr', 'rotr']}[b0][hi >> 3 & 1]
        size = {0: '.b', 1: '.w', 3: '.l'}.get(hi & 3, '.?')
        return 2, '%s%s %s' % (name, size, {'.b': RB[lo], '.w': RW[lo]}.get(size, 'er%d' % (lo & 7)))
    if b0 == 0x17:
        name = {0: 'not', 1: 'extu', 2: 'neg', 3: 'neg', 5: 'extu', 7: 'exts', 8: 'neg', 9: 'neg', 0xB: 'neg', 0xD: 'exts', 0xF: 'exts'}.get(hi, 'op17.%x' % hi)
        return 2, '%s %x' % (name, lo)
    if b0 >> 4 == 2:
        return 2, 'mov.b @0xffff%02x,%s' % (b1, RB[b0 & 15])
    if b0 >> 4 == 3:
        return 2, 'mov.b %s,@0xffff%02x' % (RB[b0 & 15], b1)
    if b0 >> 4 == 4:
        return 2, '%s 0x%05x' % (CC[b0 & 15], a + 2 + s8(b1))
    if b0 == 0x50:
        return 2, 'mulxu.b %s,%s' % (RB[hi], RW[lo])
    if b0 == 0x52:
        return 2, 'mulxu.w %s,er%d' % (RW[hi], lo & 7)
    if b0 == 0x51:
        return 2, 'divxu.b %s,%s' % (RB[hi], RW[lo])
    if b0 == 0x53:
        return 2, 'divxu.w %s,er%d' % (RW[hi], lo & 7)
    if b0 == 0x54:
        return 2, 'rts'
    if b0 == 0x55:
        return 2, 'bsr 0x%05x' % (a + 2 + s8(b1))
    if b0 == 0x56:
        return 2, 'rte'
    if b0 == 0x58:
        return 4, '%s 0x%05x' % (CC[hi], a + 4 + s16(w(2)))
    if b0 == 0x59:
        return 2, 'jmp @er%d' % (hi & 7)
    if b0 == 0x5A:
        return 4, 'jmp @0x%06x' % (l(0) & 0xFFFFFF)
    if b0 == 0x5C:
        return 4, 'bsr 0x%05x' % (a + 4 + s16(w(2)))
    if b0 == 0x5D:
        return 2, 'jsr @er%d' % (hi & 7)
    if b0 == 0x5E:
        return 4, 'jsr @0x%06x' % (l(0) & 0xFFFFFF)
    if b0 in (0x68, 0x69):
        sz, r = ('b', RB) if b0 == 0x68 else ('w', RW)
        return 2, ('mov.%s @er%d,%s' % (sz, hi, r[lo])) if hi < 8 else ('mov.%s %s,@er%d' % (sz, r[lo], hi & 7))
    if b0 in (0x6C, 0x6D):
        sz, r = ('b', RB) if b0 == 0x6C else ('w', RW)
        return 2, ('mov.%s @er%d+,%s' % (sz, hi, r[lo])) if hi < 8 else ('mov.%s %s,@-er%d' % (sz, r[lo], hi & 7))
    if b0 in (0x6E, 0x6F):
        sz, r = ('b', RB) if b0 == 0x6E else ('w', RW)
        return 4, ('mov.%s @(%d,er%d),%s' % (sz, s16(w(2)), hi, r[lo])) if hi < 8 else ('mov.%s %s,@(%d,er%d)' % (sz, r[lo], s16(w(2)), hi & 7))
    if b0 in (0x6A, 0x6B):
        sz, r = ('b', RB) if b0 == 0x6A else ('w', RW)
        if hi == 0:
            return 4, 'mov.%s @0x%04x:16,%s' % (sz, w(2), r[lo])
        if hi == 2:
            return 6, 'mov.%s @0x%06x,%s' % (sz, l(2), r[lo])
        if hi == 8:
            return 4, 'mov.%s %s,@0x%04x:16' % (sz, r[lo], w(2))
        if hi == 0xA:
            return 6, 'mov.%s %s,@0x%06x' % (sz, r[lo], l(2))
        if hi in (1, 3, 9, 0xB):
            return (6 if hi in (1, 9) else 8), 'bitop @abs %02x%02x %02x' % (b0, b1, d[a + 2])
        return 2, '.word %02x%02x' % (b0, b1)
    if 0x60 <= b0 <= 0x67 or 0x70 <= b0 <= 0x77:
        names = {0x60: 'bset', 0x61: 'bnot', 0x62: 'bclr', 0x63: 'btst', 0x70: 'bset', 0x71: 'bnot', 0x72: 'bclr', 0x73: 'btst', 0x74: 'bor', 0x75: 'bxor', 0x76: 'band', 0x77: 'bld', 0x67: 'bst'}
        return 2, '%s #%d,%s' % (names.get(b0, 'bit%02x' % b0), hi & 7, RB[lo])
    if b0 == 0x78:
        return 8, 'mov disp32 %02x %02x%02x %08x' % (b1, d[a + 2], d[a + 3], l(4))
    if b0 == 0x79:
        return 4, '%s.w #0x%04x,%s' % (IMM[hi] if hi < 7 else '?', w(2), RW[lo])
    if b0 == 0x7A:
        return 6, '%s.l #0x%06x,er%d' % (IMM[hi] if hi < 7 else '?', l(2), lo & 7)
    if b0 == 0x7B:
        return 4, 'eepmov'
    if b0 in (0x7C, 0x7D, 0x7E, 0x7F):
        return 4, 'bitop %02x%02x %02x%02x' % (b0, b1, d[a + 2], d[a + 3])
    top = b0 >> 4
    if top in IMM8:
        return 2, '%s.b #0x%02x,%s' % (IMM8[top], b1, RB[b0 & 15])
    return 2, '.word %02x%02x' % (b0, b1)


def dis(d, lo, hi, out=sys.stdout):
    a = lo
    while a < hi:
        n, t = dec(d, a)
        out.write('%05x  %-22s %s\n' % (a, d[a:a + n].hex(' '), t))
        a += n
    return a


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    data = open(sys.argv[1], 'rb').read()
    for rng in sys.argv[2:]:
        x, y = rng.split('-')
        dis(data, int(x, 16), int(y, 16))
        print('---')
