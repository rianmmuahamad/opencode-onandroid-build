#!/data/data/com.termux/files/usr/bin/bash
# Host entry point, called by the embedded terminal's login profile.
set -Eeuo pipefail
umask 077

payload=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
container=opencode-android-alpine
state="${HOME}/.local/state/opencode-android"
mkdir -p "$state"

fail() {
    local code=$?
    printf '\nSetup/peluncuran gagal (kode %s). Buka aplikasi kembali untuk mencoba lagi.\n' "$code" >&2
    printf 'Data tidak dihapus. Shell ini tersedia untuk pemeriksaan.\n' >&2
    exit "$code"
}
trap fail ERR

case "$(uname -m)" in
    aarch64|x86_64) ;;
    *) printf 'Prototipe ini membutuhkan sistem ARM64 atau x86_64.\n' >&2; exit 1 ;;
esac
command -v pkg >/dev/null || { printf 'Jalankan di lingkungan aplikasi berbasis Termux.\n' >&2; exit 1; }

# flock guards the long-running setup/session. The OS releases the lock if
# Android kills the process, so a later launch does not inherit a stale lock.
if ! command -v flock >/dev/null; then
    printf '[1/4] Menyiapkan pengunci sesi...\n'
    pkg install -y util-linux
fi
exec 9>"$state/session.lock"
if ! flock -n 9; then
    printf 'OpenCode atau setup masih aktif di sesi lain. Pilih sesi tersebut dari daftar terminal.\n'
    exit 0
fi

if ! command -v proot-distro >/dev/null; then
    printf '[1/4] Memasang proot-distro...\n'
    pkg install -y proot-distro
fi

if ! proot-distro login "$container" -- /bin/true >/dev/null 2>&1; then
    printf '[2/4] Menyiapkan Alpine Linux...\n'
    install_help=$(proot-distro install --help 2>&1)
    if [[ "$install_help" == *'--name'* ]]; then
        # Current OCI-based proot-distro.
        proot-distro install alpine:3.23 --name "$container"
    elif [[ "$install_help" == *'--override-alias'* ]]; then
        # Older distro-plugin implementation.
        proot-distro install --override-alias "$container" alpine
    else
        printf 'Versi proot-distro belum didukung; instalasi dihentikan.\n' >&2
        exit 1
    fi
fi

printf '[3/4] Memeriksa OpenCode...\n'
proot-distro login --bind "$payload:/opt/opencode-android" "$container" -- \
    /bin/sh /opt/opencode-android/guest-setup.sh

printf '[4/4] Membuka OpenCode...\n'
# Keep this process and its lock alive while PRoot runs; do not exec a program
# that could close fd 9. No pipe is used: the TUI keeps its terminal/PTY.
proot-distro login --bind "$payload:/opt/opencode-android" "$container" -- \
    /bin/bash /opt/opencode-android/guest-run.sh "$@"
