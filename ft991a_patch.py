#!/usr/bin/env python3
"""FT-991A SPECTRUM GAIN patcher (SP9TKN).

Builds patched firmware files from YOUR copies of Yaesu's official FT-991A firmware (download them from yaesu.com):
  MAIN V02-07  (FT-991A_MAIN_V0207.zip  -> AH067_V0207.SFL)        SPECTRUM GAIN menu item, C.S long press
  TFT  V02-00  (FT-991A_TFW_V0200.zip   -> TFT_AH067M_V02-00.bin)  gain on the waterfall and spectra, value on screen
  DSP  V01-12  (FT-991A_DSP_V0112.zip   -> AH067_V0112.dat)        optional: gentler DNR (12 coefficients, see
                                                                     tools/dsp_dnr.py for their source)
This repository contains no Yaesu code; it only applies the patches.

  python ft991a_patch.py --main FT-991A_MAIN_V0207.zip --tft FT-991A_TFW_V0200.zip --out patched
  python ft991a_patch.py --dsp FT-991A_DSP_V0112.zip --out patched

MAIN and TFT belong together (the TFT reads the gain from MAIN), the DSP part is independent.
Nothing is written to the radio. Flash the results with Yaesu's own programs (YFSW024 for MAIN, TFW for TFT,
FW-DSP for DSP) at your own risk, after backing up the menu settings and memories.
"""
import argparse
import hashlib
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))

import build_test as b      # noqa: E402  base: decode/encode SFL, menu item 154, TFT gain hook (test_03)
import build_test08 as b8   # noqa: E402  C.S long press = gain on MULTI
import build_test09 as b9   # noqa: E402  gain number in the spectrum corner (constants, font)
import build_test10 as b10  # noqa: E402  mode state byte for the TFT, number only while the mode is on
import dsp_dnr              # noqa: E402  DSP: gentler DNR coefficients

SFL_NAME, TFT_NAME, DSP_NAME = "AH067_V0207.SFL", "TFT_AH067M_V02-00.bin", "AH067_V0112.dat"
SHA_IN = {
    SFL_NAME: "17e24a1a96403c9e8a2075db0ccd6586a1591404fa62239178c491d7ef4622cd",   # MAIN V02-07 from yaesu.com
    TFT_NAME: "7df2119ce0d9b9074b1a0720bc20bf6f0189696884b2a8cc069fdf5104582fd4",   # TFT V02-00 from yaesu.com
    DSP_NAME: "56e9440031339a0d05711ce19a93df6eacc479592734be6da40e925d503dc2c5",   # DSP V01-12 from yaesu.com
}
SHA_OUT = {
    SFL_NAME: "56d0174e96d1a8623774ea7230e1602315b1c9beb2001cba2c00536ce97edd8b",   # = the author's test_11 MAIN
    TFT_NAME: "34daa13d1375e9caa8d9bbd6918336ba2775819fe58bd2ab38eaea505cb29607",   # = the author's test_10 TFT
    DSP_NAME: "5e1b4954c90fe68c7f74277b876ce99f275074c0021e8d4a200fbfcda64b90b4",   # = the DNR file in the radio
}


def read_input(path: Path, name: str) -> bytes:
    """The firmware file itself, or Yaesu's zip that contains it."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            hits = [i for i in z.namelist() if i.replace("\\", "/").split("/")[-1] == name]
            if not hits:
                sys.exit(f"{path.name}: no {name} inside")
            data = z.read(hits[0])
    else:
        data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != SHA_IN[name]:
        sys.exit(f"{name}: this is not the expected official file (SHA-256 {sha}). "
                 f"Only MAIN V02-07, TFT V02-00 and DSP V01-12 of the FT-991A are supported.")
    return data


def build_main_tft(sfl: bytes, tft: bytes, out: Path):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / SFL_NAME).write_bytes(sfl)
        (tmp / TFT_NAME).write_bytes(tft)
        step = tmp / "step03"
        step.mkdir()
        # 1) base (test_03): menu item 154 SCOPE SPECTRUM GAIN in MAIN, gain applied to waterfall and spectra in TFT
        b.SFL_IN, b.TFT_IN, b.OUT = tmp / SFL_NAME, tmp / TFT_NAME, step
        b.main()
        # 2) TFT (test_10): the gain number in the spectrum corner, shown only while the C.S mode is on
        b9.IN = step / TFT_NAME
        b10.OUT = out
        b10.build_tft()
        # 3) MAIN (test_11): C.S long press = gain on MULTI, the mode ends about 1 s after the last turn
        b8.TICKS = 100
        b10.build_main()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--main", type=Path, help="FT-991A_MAIN_V0207.zip or AH067_V0207.SFL")
    ap.add_argument("--tft", type=Path, help="FT-991A_TFW_V0200.zip or TFT_AH067M_V02-00.bin")
    ap.add_argument("--dsp", type=Path, help="optional: FT-991A_DSP_V0112.zip or AH067_V0112.dat")
    ap.add_argument("--out", default=Path("patched"), type=Path, help="output folder (default: patched)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if bool(a.main) != bool(a.tft):
        ap.error("--main and --tft go together (the TFT reads the gain from MAIN)")
    if not (a.main or a.dsp):
        ap.error("give --main and --tft, --dsp, or all three")

    done = []
    a.out.mkdir(parents=True, exist_ok=True)
    if a.main:
        build_main_tft(read_input(a.main, SFL_NAME), read_input(a.tft, TFT_NAME), a.out)
        done += [SFL_NAME, TFT_NAME]
    if a.dsp:
        (a.out / DSP_NAME).write_bytes(dsp_dnr.patch_dsp(read_input(a.dsp, DSP_NAME)))
        done.append(DSP_NAME)

    ok = True
    for name in done:
        sha = hashlib.sha256((a.out / name).read_bytes()).hexdigest()
        same = sha == SHA_OUT[name]
        ok &= same
        print(f"{name}: SHA-256 {sha} {'OK (identical to the tested files)' if same else 'DIFFERENT - do not flash'}")
    if not ok:
        sys.exit(1)
    print(f"Done: {a.out.resolve()}")


if __name__ == "__main__":
    main()
