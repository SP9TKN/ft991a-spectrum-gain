"""FT-991A DSP V01-12: gentler DNR (12 coefficients).

Applies the DNR coefficients of the "FT991A_DSP_V0112_DNR_NEWGEN_BACKPORT" package published on radio.xreflector.es
(its author is not named there). The package documents these exact words in its PATCH_DIFF.txt: they are the DNR
coefficients of the FTDX10 IFDSP V01-20, written into the FT-991A DSP table. Only these numbers are used here; the
DSP file itself comes from your own copy of Yaesu's FT-991A_DSP_V0112.zip.

File layout (AH067_V0112.dat): bytes 0-3 = file length, bytes 4-7 = 32-bit sum of all bytes from offset 8, both
little-endian; the coefficients are little-endian IEEE 754 floats too (PATCH_DIFF.txt lists them as hex numbers).
"""
import struct

# (file offset, original word, new word) — DSP addresses 0x1181E8AC.. (bank A) and 0x1181E8F4.. (bank B)
DNR_WORDS = [
    (0x016C40, 0x3F7F41F2, 0x3F7FEF9E),   # DNR 1 A  0.997100 -> 0.999750
    (0x016C44, 0x3F7F41F2, 0x3F7FEC57),   # DNR 2 A  0.997100 -> 0.999700
    (0x016C48, 0x3F7F41F2, 0x3F7FE910),   # DNR 3 A  0.997100 -> 0.999650
    (0x016C4C, 0x3F7EB852, 0x3F7FE5C9),   # DNR 4 A  0.995000 -> 0.999600
    (0x016C50, 0x3F7EF9DB, 0x3F7FE282),   # DNR 5 A  0.996000 -> 0.999550
    (0x016C54, 0x3F7F1AA0, 0x3F7FDF3B),   # DNR 6 A  0.996500 -> 0.999500
    (0x016C58, 0x3F7F3B64, 0x3F7FDBF5),   # DNR 7 A  0.997000 -> 0.999450
    (0x016C5C, 0x3F7F5C29, 0x3F7FD8AE),   # DNR 8 A  0.997500 -> 0.999400
    (0x016C88, 0x3F51EB85, 0x3F6B851F),   # DNR 1 B  0.820000 -> 0.920000
    (0x016C8C, 0x3F3D70A3, 0x3F5EB852),   # DNR 2 B  0.740000 -> 0.870000
    (0x016C90, 0x3F28F5C2, 0x3F51EB85),   # DNR 3 B  0.660000 -> 0.820000
    (0x016C94, 0x3F1EB851, 0x3F451EB8),   # DNR 4 B  0.620000 -> 0.770000
]


def patch_dsp(data: bytes) -> bytes:
    d = bytearray(data)
    assert struct.unpack_from("<I", d, 0)[0] == len(d), "unexpected DSP file length field"
    assert struct.unpack_from("<I", d, 4)[0] == sum(d[8:]) & 0xFFFFFFFF, "DSP checksum does not match the file"
    for off, old, new in DNR_WORDS:
        assert struct.unpack_from("<I", d, off)[0] == old, f"unexpected word at 0x{off:06X}"
        struct.pack_into("<I", d, off, new)
    struct.pack_into("<I", d, 4, sum(d[8:]) & 0xFFFFFFFF)
    return bytes(d)
