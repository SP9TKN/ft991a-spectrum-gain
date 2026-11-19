"""Buduje pliki testowe SPECTRUM GAIN dla FT-991A (MAIN V02-07 + TFT V02-00). NIC NIE WGRYWA."""
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / 'work'   # ft991a_patch.py sets the real paths
SFL_IN = ROOT / 'analiza/main/AH067_V0207.SFL'
TFT_IN = ROOT / 'analiza/tft/TFT_AH067M_V02-00.bin'
OUT = ROOT / 'test_03'

KEY = bytes([30, 39, 27, 18, 17, 22, 25, 23, 36, 37, 41, 28, 13, 11, 6, 4, 3, 1, 2, 5, 7, 12, 14, 15, 24, 29, 32, 34, 42,
             43, 8, 9, 10, 16, 19, 20, 21, 26, 31, 33, 40, 35, 38])
FLASH_END = 0x60000
OLD_TOP = 0x3D808
CELL = 0xFFB45F          # RAM komorki 0x0274 z mapy pamieci
MENU_OLD = 0x1A540
NEW_TEXT = b'154 SCOPE       SPECTRUM GAIN           '
TFT_BASE = 0x0C000000
TFT_STUB = 0x0C001C00
TFT_LITS = (0x0C015AC0, 0x0C015D4C, 0x0C015FD0)  # wywolania get(33) w widmie 59, widmie 29 i waterfallu
TFT_GET = 0x0C019D02
TFT_L_ADDR = 0x0C31CFD9  # kopia bloku 0x21 w TFT + 16


def enc(line, rot):
    return bytes((c + KEY[(rot + i) % 43]) & 255 for i, c in enumerate(line))


def dec(line, rot):
    return bytes((c - KEY[(rot + i) % 43]) & 255 for i, c in enumerate(line))


def parse_sfl(raw):
    """Zwraca liste linii z rotacja klucza; klucz biegnie ciagle po znakach bez CRLF, start 41."""
    lines = raw.split(b'\r\n')
    rot = 41
    out = []
    first = True
    for line in lines:
        if line.startswith(b';') or not line:
            out.append(('raw', line, None))
            continue
        out.append(('rec0' if first else 'rec', line, rot))
        first = False
        rot = (rot + len(line)) % 43
    return out


def srec(addr, data):
    body = bytes([len(data) + 4]) + addr.to_bytes(3, 'big') + data
    return b'S2' + body.hex().upper().encode() + b'%02X' % ((~sum(body)) & 255)


def rec_fields(text):
    b = bytes.fromhex(text[2:].decode())
    k = int(chr(text[1]))
    al = {0: 2, 1: 2, 2: 3, 3: 4, 7: 4, 8: 3, 9: 2}[k]
    return k, int.from_bytes(b[1:1 + al], 'big'), b[1 + al:-1]


def rebuild(raw, img, top):
    """Sklada SFL z obrazu; linie niezmienione pozostaja bajt w bajt."""
    items = parse_sfl(raw)
    out = []
    rot = 41
    last_addr_end = None
    tail_s9 = None
    for kind, line, r in items:
        if kind == 'raw':
            out.append(line)
            continue
        if kind == 'rec0':
            out.append(line)
            rot = (rot + len(line)) % 43
            continue
        text = dec(line, r)
        k, addr, data = rec_fields(text)
        if k in (7, 8, 9):
            tail_s9 = text
            # dopisz nowe rekordy przed S9
            a = last_addr_end
            while a < top:
                n = min(16, top - a)
                t = srec(a, bytes(img[a:a + n]))
                out.append(enc(t, rot))
                rot = (rot + len(t)) % 43
                a += n
            out.append(enc(text, rot))
            rot = (rot + len(text)) % 43
            continue
        new = bytes(img[addr:addr + len(data)])
        if new != data:
            b = bytes.fromhex(text[2:-2].decode()) + b''
            b = b[:len(b) - len(data)] + new
            text = text[:2] + b.hex().upper().encode() + b'%02X' % ((~sum(b)) & 255)
        out.append(enc(text, rot))
        rot = (rot + len(text)) % 43
        last_addr_end = addr + len(data)
    assert tail_s9 is not None
    return b'\r\n'.join(out)


def image_from(raw):
    mem = bytearray(b'\xff' * FLASH_END)
    top = 0
    for kind, line, r in parse_sfl(raw):
        if kind != 'rec':
            continue
        k, addr, data = rec_fields(dec(line, r))
        if k in (1, 2, 3):
            mem[addr:addr + len(data)] = data
            top = max(top, addr + len(data))
    return mem, top


def set_checksum(raw, img):
    s = sum(img[:FLASH_END]) & 0xFFFFFFFF
    new, n = re.subn(rb'(\[CHECK SUM\]\s+)[0-9A-F]{8}', lambda m: m.group(1) + b'%08X' % s, raw, count=1)
    assert n == 1
    return new, s


def patch(img, addr, old, new):
    assert bytes(img[addr:addr + len(old)]) == bytes(old), hex(addr)
    assert len(old) == len(new)
    img[addr:addr + len(new)] = new


def j24(op, a):
    return bytes([op]) + a.to_bytes(3, 'big')


def build_main(img):
    cell = CELL.to_bytes(4, 'big')
    ldl1 = b'\x7a\x01' + cell
    p = 0x3D810
    h = {}

    def put(name, code):
        nonlocal p
        h[name] = p
        img[p:p + len(code)] = code
        p += len(code)

    # handlery (wzor: menu 120 PRMTRC EQ1 LEVEL, zakres -20..+20)
    put('A', ldl1 + bytes.fromhex('6818 0a08 4a06 a8ec 4506 4006 a815 4502 f814 6898 5470'))
    put('B', ldl1 + bytes.fromhex('6818 1a08 4a06 a8ec 4506 4006 a815 4502 f8ec 6898 5470'))
    put('C', b'\x6a\x28' + cell + b'\xa8\x00' + j24(0x5A, 0x183F6))
    put('D', b'\xf8\x00\x6a\xa8' + cell + b'\x54\x70')
    put('E', ldl1 + j24(0x5A, 0x1A200))
    put('TX', b'\x6a\x28' + cell + bytes.fromhex('01736ca8 0bf2 5470'))
    # stuby przelacznika: indeks 153 -> nowy handler, reszta -> oryginalny pomocnik
    for n in 'ABCDE':
        put('S' + n, bytes.fromhex('a899 4606 0b97') + j24(0x5A, h[n]) + j24(0x5A, 0x2C38E))
    # tabela menu zostaje na miejscu; indeks 153 dostaje osobny tekst
    menu_new = p + 18
    put('T', b'\x7a\x11' + MENU_OLD.to_bytes(4, 'big') + bytes.fromhex('a899 4606 7a01') + menu_new.to_bytes(4, 'big') + b'\x54\x70')
    assert p == menu_new and len(NEW_TEXT) == 40
    img[menu_new:menu_new + 40] = NEW_TEXT
    top = menu_new + 40
    assert top < FLASH_END

    sw = j24(0x5E, 0x2C38E)
    for site, n in [(0x16A06, 'A'), (0x175F8, 'B'), (0x1817E, 'C'), (0x18C32, 'D'), (0x19640, 'E')]:
        assert bytes(img[site + 4:site + 6]) == b'\x00\x98', hex(site)
        patch(img, site, sw, j24(0x5E, h['S' + n]))
    patch(img, 0x16978, b'\xa8\x99', b'\xa8\x9a')
    patch(img, 0x169A4, b'\xf8\x98', b'\xf8\x99')
    patch(img, 0x2E2C6, b'\x88\x99', b'\x88\x9a')
    patch(img, 0x2E2E4, b'\xa8\x99', b'\xa8\x9a')
    patch(img, 0x2E332, b'\xa8\x99', b'\xa8\x9a')
    patch(img, 0x2E300, b'\x7a\x11' + MENU_OLD.to_bytes(4, 'big'), j24(0x5E, h['T']) + b'\x00\x00')
    patch(img, 0x2F936, bytes.fromhex('0b72 0bf2'), j24(0x5A, h['TX']))
    return top, h, menu_new


def sh_stub():
    # zmienia sygnal v na stosie funkcji rysujacej @(4,r15), potem skacze do oryginalnego get(33); r4 nietkniety
    w = [0xD112, 0x6110, 0x2118, 0x891E,
         0xE514, 0x3157, 0x891B,
         0xE5EC, 0x3517, 0x8918,
         0x84F4, 0x630C, 0x6213, 0xE009, 0x4280, 0x332C, 0xE6FF, 0x666C,
         0x4115, 0x8909,
         0x4311, 0x8900, 0xE300,
         0x611B, 0x6013, 0x4000, 0xD506, 0x005D, 0x4380, 0x4319,
         0x3363, 0x8B00, 0x6363,
         0x6033, 0x80F4,
         0xD303, 0x432B, 0x0009]
    code = struct.pack('>%dH' % len(w), *w)
    assert len(code) == 76
    code += struct.pack('>III', TFT_L_ADDR, TFT_STUB + 88, TFT_GET)
    # zaokraglenie w gore: najsilniejszy sygnal ma dojsc do najwyzszego koloru
    scale = [0] + [-(-255 * 256 // (255 - 9 * n)) for n in range(1, 21)]
    return code + struct.pack('>21H', *scale)


def build_tft(d):
    stub = sh_stub()
    o = TFT_STUB - TFT_BASE
    assert d[o:o + len(stub)] == b'\x00' * len(stub)
    assert o + len(stub) < 0x2000
    d[o:o + len(stub)] = stub
    for lit in TFT_LITS:
        lo = lit - TFT_BASE
        assert struct.unpack('>I', d[lo:lo + 4])[0] == TFT_GET
        d[lo:lo + 4] = struct.pack('>I', TFT_STUB)


def main():
    raw = SFL_IN.read_bytes()
    img, top0 = image_from(raw)
    assert top0 == OLD_TOP
    # kontrola: bez zmian koder ma odtworzyc oryginal bajt w bajt
    assert rebuild(raw, img, top0) == raw, 'koder nie odtwarza oryginalu'
    top, h, menu_new = build_main(img)
    sfl = rebuild(raw, img, top)
    sfl, s = set_checksum(sfl, img)
    OUT.mkdir(exist_ok=True)
    (OUT / 'AH067_V0207.SFL').write_bytes(sfl)
    t = bytearray(TFT_IN.read_bytes())
    build_tft(t)
    (OUT / 'TFT_AH067M_V02-00.bin').write_bytes(t)
    print('MAIN top', hex(top), 'suma %08X' % s, 'menu', hex(menu_new), {k: hex(v) for k, v in h.items()})


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
