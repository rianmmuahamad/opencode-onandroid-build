#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
build_root="$root/build"
source_dir="$build_root/termux-app"
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$build_root/gradle-home}"
export ANDROID_USER_HOME="${ANDROID_USER_HOME:-$build_root/android-home}"
mode="${1:-build}"
if [[ "$mode" != build && "$mode" != --prepare ]]; then
    printf 'Penggunaan: bash tools/build-android.sh [--prepare]\n' >&2
    exit 2
fi

for tool in java git python3; do
    command -v "$tool" >/dev/null || { printf 'Dependency belum tersedia: %s\n' "$tool" >&2; exit 1; }
done
mkdir -p "$build_root"
if [[ ! -d "$source_dir/.git" ]]; then
    git clone --depth 1 --branch v0.118.3 https://github.com/termux/termux-app.git "$source_dir"
fi
if [[ "$(git -C "$source_dir" rev-parse HEAD)" != 5b657c6adf4304e5198951ce815fe0205dcac29c ]]; then
    printf 'Commit upstream tidak sesuai tag v0.118.3; hentikan build.\n' >&2
    exit 1
fi
if [[ "$mode" == --prepare ]]; then
    printf 'Source upstream siap: %s\n' "$source_dir"
    exit 0
fi
sdk_path="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
if [[ -z "$sdk_path" || ! -d "$sdk_path/platforms" ]]; then
    printf 'SDK Android belum tersedia. Atur ANDROID_HOME ke SDK lengkap dari Android Studio.\n' >&2
    exit 1
fi
# Never reset or clean an existing developer checkout. The patcher is idempotent.
python3 "$root/tools/prepare-android.py" brand "$source_dir"
(
    cd "$source_dir"
    ./gradlew :app:downloadBootstraps --no-daemon
)
python3 "$root/tools/prepare-android.py" inject "$source_dir"
(
    cd "$source_dir"
    ./gradlew :app:assembleDebug --no-daemon
)
mkdir -p "$root/dist"
python3 "$root/tools/prepare-android.py" collect "$source_dir" "$root/dist"
printf '\nAPK dan arsip source build tersedia di %s/dist\n' "$root"
