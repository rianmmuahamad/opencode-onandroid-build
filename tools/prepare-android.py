#!/usr/bin/env python3
"""Add our own runtime to checksum-verified upstream Termux bootstraps.

No upstream source is vendored here. Build the terminal with its original
package identity so that its compiled package prefix remains correct.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MARKER = b"# BEGIN OPENCODE ANDROID\n"
PAYLOAD = ("start.sh", "guest-setup.sh", "guest-run.sh")


def brand(source):
    path = source / "app/src/main/res/values/strings.xml"
    content = path.read_text()
    content, count = re.subn(
        r'(<string\s+name="application_name"[^>]*>)[^<]*(</string>)',
        r'\g<1>OpenCode Android\2', content,
    )
    if count != 1:
        raise ValueError("Struktur application_name upstream berubah; tinjau patch.")
    path.write_text(content)


def patch_zip(path):
    with zipfile.ZipFile(path) as archive:
        entries = [(item, archive.read(item)) for item in archive.infolist()]
    files = {item.filename: data for item, data in entries}
    if "etc/profile" not in files:
        raise ValueError(f"Bootstrap tanpa etc/profile: {path}")
    profile = files["etc/profile"]
    if MARKER in profile:
        profile = profile.split(MARKER)[0]
    profile = profile.rstrip(b"\n") + b"\n" + MARKER
    profile += (ROOT / "runtime/profile-hook.sh").read_bytes()
    additions = {f"libexec/opencode-android/{name}": (ROOT / "runtime" / name).read_bytes()
                 for name in PAYLOAD}
    temporary = path.with_suffix(".new.zip")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item, data in entries:
            if item.filename in additions:
                continue
            archive.writestr(item, profile if item.filename == "etc/profile" else data)
        for name, data in additions.items():
            # Called explicitly with bash/sh, so executable mode is unnecessary.
            archive.writestr(name, data)
    temporary.replace(path)


def inject(source):
    gradle = source / "app/build.gradle"
    content = gradle.read_text()
    archives = sorted((source / "app/src/main/cpp").glob("bootstrap-*.zip"))
    if not archives:
        raise ValueError("Jalankan :app:downloadBootstraps dahulu.")
    manifest = {}
    validated = []
    for archive in archives:
        arch = archive.stem.removeprefix("bootstrap-")
        old_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        # Only accept a file the upstream Gradle checksum table would accept.
        pattern = re.compile(r'(downloadBootstrap\(\s*[\'"]' + re.escape(arch)
                             + r'[\'"]\s*,\s*[\'"])([0-9a-f]{64})([\'"])')
        matches = list(pattern.finditer(content))
        if old_digest not in [match[2] for match in matches]:
            raise ValueError(f"Checksum bootstrap tidak dikenal: {arch}")
        validated.append((archive, arch, old_digest, pattern))
    # Validate the entire input set before changing any archive.
    for archive, arch, old_digest, pattern in validated:
        patch_zip(archive)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        content = pattern.sub(lambda m: m[1] + (digest if m[2] == old_digest else m[2]) + m[3], content)
        manifest[arch] = {"input_sha256": old_digest, "patched_sha256": digest}
    gradle.write_text(content)
    (source / "opencode-bootstrap-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def collect(source, output):
    output.mkdir(parents=True, exist_ok=True)
    apks = sorted((source / "app/build/outputs/apk/debug").rglob("*.apk"))
    if not apks:
        raise ValueError("Build tidak menghasilkan APK debug.")
    for apk in apks:
        shutil.copy2(apk, output / ("opencode-android_" + apk.name))
    # Keep the exact modified corresponding source beside experimental APKs.
    target = output / "opencode-android-corresponding-source.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for base, prefix in ((source, "termux-app"), (ROOT, "opencode-overlay")):
            for path in sorted(base.rglob("*")):
                relative = path.relative_to(base)
                if any(part in {".git", ".gradle", "build", "dist", "__pycache__"} for part in relative.parts):
                    continue
                if path.is_file():
                    archive.write(path, str(Path(prefix) / relative))


if __name__ == "__main__":
    action, source = sys.argv[1], Path(sys.argv[2]).resolve()
    if action == "brand":
        brand(source)
    elif action == "inject":
        inject(source)
    elif action == "collect":
        collect(source, Path(sys.argv[3]).resolve())
    else:
        raise SystemExit("Gunakan brand, inject, atau collect.")
