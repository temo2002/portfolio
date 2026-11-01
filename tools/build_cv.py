#!/usr/bin/env python3
"""Kompilerer cv/main.tex til cv/Temmam_Altaie_CV.pdf (krever pdflatex).

Hopper over stille hvis pdflatex ikke finnes, slik at resten av bygget går som vanlig.
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "cv" / "main.tex"
OUT = ROOT / "cv" / "Temmam_Altaie_CV.pdf"
STAMP = ROOT / "cv" / ".main.tex.md5"


def main():
    if not SRC.exists():
        print("Ingen cv/main.tex, hopper over.")
        return
    digest = hashlib.md5(SRC.read_bytes()).hexdigest()
    if OUT.exists() and STAMP.exists() and STAMP.read_text().strip() == digest:
        print("CV-en er uendret.")
        return
    if not shutil.which("pdflatex"):
        print("pdflatex mangler, hopper over CV-bygget.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(2):
            r = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", tmp, str(SRC)],
                capture_output=True, text=True, cwd=SRC.parent,
            )
            if r.returncode:
                print(r.stdout[-2000:])
                sys.exit("CV-en kunne ikke kompileres.")
        OUT.write_bytes((Path(tmp) / "main.pdf").read_bytes())
    STAMP.write_text(digest + "\n")
    print(f"Skrev {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
