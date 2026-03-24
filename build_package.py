"""Build a distributable package of the Alphacam Knowledge Base."""

import shutil
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
PDF_SRC = Path(r"C:/Users/agoodger/Downloads/PDFs")
OUT_DIR = Path.home() / "AlphacamKB_dist" / "AlphacamKB"

FILES = [
    "db_server.py",
    "knowledge_base.db",
    "launch.bat",
    "install.bat",
]

DIRS = [
    "ui",
    "kb_images",
]


def main():
    if OUT_DIR.exists():
        print(f"Removing old package: {OUT_DIR}")
        for attempt in range(5):
            try:
                shutil.rmtree(OUT_DIR)
                break
            except PermissionError:
                if attempt < 4:
                    print(f"  Folder locked (OneDrive?), retrying in 2s...")
                    time.sleep(2)
                else:
                    raise

    OUT_DIR.mkdir(parents=True)
    print(f"Building package in: {OUT_DIR}")

    # Copy files
    for f in FILES:
        src = SRC_DIR / f
        if src.exists():
            shutil.copy2(src, OUT_DIR / f)
            print(f"  Copied {f}")
        else:
            print(f"  WARNING: {f} not found, skipping")

    # Copy directories
    for d in DIRS:
        src = SRC_DIR / d
        if src.exists():
            shutil.copytree(src, OUT_DIR / d)
            count = sum(1 for _ in (OUT_DIR / d).rglob("*") if _.is_file())
            print(f"  Copied {d}/ ({count} files)")
        else:
            print(f"  WARNING: {d}/ not found, skipping")

    # Copy PDFs
    pdf_out = OUT_DIR / "pdfs"
    if PDF_SRC.exists():
        pdf_out.mkdir()
        pdf_count = 0
        for pdf in PDF_SRC.glob("*.pdf"):
            shutil.copy2(pdf, pdf_out / pdf.name)
            pdf_count += 1
        print(f"  Copied pdfs/ ({pdf_count} PDFs)")
    else:
        print(f"  WARNING: PDF source {PDF_SRC} not found, skipping")

    # Copy flowchart
    flowchart = SRC_DIR / "install_guide.html"
    if flowchart.exists():
        shutil.copy2(flowchart, OUT_DIR / flowchart.name)
        print(f"  Copied install_guide.html")

    # Calculate total size
    total = sum(f.stat().st_size for f in OUT_DIR.rglob("*") if f.is_file())
    print(f"\nPackage built: {OUT_DIR}")
    print(f"Total size: {total / 1024 / 1024:.1f} MB")
    print(f"\nTo distribute: copy the AlphacamKB folder to the target PC")
    print(f"then run install.bat from inside it.")


if __name__ == "__main__":
    main()
