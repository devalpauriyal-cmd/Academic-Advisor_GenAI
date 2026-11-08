"""Check publishable files for credential patterns and GitHub file-size limits.

Run from any directory: python scripts/check_repository.py [--history]
Only file paths and finding categories are printed, never matching secret values.
This heuristic check does not prove that all sensitive content is absent.
"""
import argparse
import re
import subprocess
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from io import BytesIO

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "Groq API key": rb"gsk_[A-Za-z0-9]{20,}",
    "Google API key": rb"AIza[0-9A-Za-z_-]{30,}",
    "GitHub token": rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})",
    "AWS access-key ID": rb"(?:AKIA|ASIA)[0-9A-Z]{16}",
    "private key": rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "credential in URL": rb"https?://[^\s/:]+:[^\s/@]{8,}@",
}
PRIVATE_PARTS = {".local-backups", ".local-artifacts", ".aws", ".ssh", ".venv", "node_modules"}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def findings(data):
    return [label for label, pattern in PATTERNS.items() if re.search(pattern, data)]


def content_findings(data, name):
    result = findings(data)
    if name.endswith((".docx", ".xlsx")):
        try:
            with ZipFile(BytesIO(data)) as archive:
                for entry in archive.infolist():
                    if entry.filename.endswith((".xml", ".rels")):
                        result.extend(findings(archive.read(entry)))
        except BadZipFile:
            result.append("invalid Office archive")
    return sorted(set(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="also inspect reachable Git blobs")
    args = parser.parse_args()
    names = set(filter(None, git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")))
    errors, checked = [], 0
    for name in sorted(names):
        path = ROOT / name
        if not path.is_file():
            continue
        checked += 1
        if set(Path(name).parts) & PRIVATE_PARTS or (path.name.startswith(".env") and not path.name.endswith(".example")):
            errors.append((name, "private/local file is eligible for commit"))
        data = path.read_bytes()
        if len(data) >= 100 * 1024 * 1024:
            errors.append((name, "file reaches/exceeds 100 MiB"))
        errors.extend((name, label) for label in content_findings(data, name))
    history_count = 0
    if args.history:
        objects = git("rev-list", "--objects", "--all").splitlines()
        with subprocess.Popen(["git", "-C", str(ROOT), "cat-file", "--batch"],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
            try:
                for entry in objects:
                    oid, _, name = entry.partition(b" ")
                    process.stdin.write(oid + b"\n")
                    process.stdin.flush()
                    header = process.stdout.readline().split()
                    if len(header) != 3:
                        raise RuntimeError("Unexpected response from git cat-file")
                    data = process.stdout.read(int(header[2]))
                    process.stdout.read(1)
                    if header[1] == b"blob":
                        history_count += 1
                        label = name.decode(errors="replace") or oid.decode()
                        errors.extend(("history:" + label, item) for item in content_findings(data, label))
            finally:
                process.stdin.close()
                process.wait()
    for name, label in sorted(set(errors)):
        print(f"FAIL {name}: {label}")
    print(f"Checked {checked} current files and {history_count} historical blobs; {len(set(errors))} findings.")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
