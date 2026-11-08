"""Create a local review ZIP from Git-eligible files, excluding credentials/caches.

Run: python scripts/package_repository.py
This creates no commit, changes no remote, and uploads nothing.
"""
import csv
import hashlib
import io
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "FILE_INVENTORY.csv"
OUTPUT = ROOT / ".local-artifacts" / "alice-ai-academic-advisor.zip"


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "check_repository.py")], check=True)
    raw = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "--cached", "--others",
                                   "--exclude-standard", "-z"])
    names = sorted(set(filter(None, raw.decode().split("\0"))))
    names = [name for name in names if (ROOT / name).is_file() and ROOT / name != MANIFEST]
    rows = []
    for name in names:
        data = (ROOT / name).read_bytes()
        rows.append((name, len(data), hashlib.sha256(data).hexdigest()))
    content = io.StringIO(newline="")
    writer = csv.writer(content, lineterminator="\n")
    writer.writerow(["path", "bytes", "sha256"])
    writer.writerows(rows)
    MANIFEST.write_text(content.getvalue(), encoding="utf-8")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for name in names + [MANIFEST.relative_to(ROOT).as_posix()]:
            archive.write(ROOT / name, "alice-ai-academic-advisor/" + name)
    with ZipFile(OUTPUT) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Archive CRC check failed: {bad}")
        for name, size, expected in rows:
            data = archive.read("alice-ai-academic-advisor/" + name)
            if len(data) != size or hashlib.sha256(data).hexdigest() != expected:
                raise RuntimeError(f"Archive content check failed: {name}")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    OUTPUT.with_suffix(".zip.sha256").write_text(f"{digest}  {OUTPUT.name}\n", encoding="utf-8")
    print(f"Created {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size / 1024**2:.2f} MiB)")
    print(f"Verified {len(rows) + 1} archive entries; SHA-256: {digest}")


if __name__ == "__main__":
    main()
