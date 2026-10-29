#!/data/data/com.termux/files/usr/bin/bash
# Install in Termux, then start OpenCode in Alpine.
set -Eeuo pipefail
umask 077
command -v pkg >/dev/null || { printf 'Jalankan installer ini di Termux.\n' >&2; exit 1; }
install_dir="$HOME/.local/share/opencode-android"
mkdir -p "$install_dir" "$PREFIX/bin"
cat > "$install_dir/start.sh" <<'OPENCODE_ANDROID_start_sh'
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
    printf '\nSetup/peluncuran gagal (kode %s). Jalankan opencode-android untuk mencoba lagi.\n' "$code" >&2
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
OPENCODE_ANDROID_start_sh
cat > "$install_dir/guest-setup.sh" <<'OPENCODE_ANDROID_guest_setup_sh'
#!/bin/sh
set -eu
umask 077
state="$HOME/.local/state/opencode-android"
binary="$HOME/.opencode/bin/opencode"
if [ -f "$state/ready-v1" ] && [ -x "$binary" ]; then
    exit 0
fi

printf 'Memasang Bash, curl, Git, dan dependensi Alpine...\n'
apk add --no-cache bash curl ca-certificates git ripgrep libstdc++ libgcc

mkdir -p "$state"
if [ ! -x "$binary" ]; then
    printf 'Mengunduh installer resmi OpenCode 1...\n'
    installer=$(mktemp)
    trap 'rm -f "$installer"' EXIT HUP INT TERM
    # Download first: a failed download must never execute a partial installer.
    curl --fail --show-error --location --retry 3 --connect-timeout 20 \
        https://opencode.ai/install -o "$installer"
    bash "$installer" --no-modify-path
fi
"$binary" --version
mkdir -p "$HOME/projects"
# Mark ready only after a successful runtime smoke test.
printf 'OpenCode 1; Alpine; setup revision 1\n' > "$state/ready-v1.tmp"
mv "$state/ready-v1.tmp" "$state/ready-v1"
OPENCODE_ANDROID_guest_setup_sh
cat > "$install_dir/guest-run.sh" <<'OPENCODE_ANDROID_guest_run_sh'
#!/bin/bash
set -euo pipefail
export PATH="$HOME/.opencode/bin:$PATH"
export TERM="${TERM:-xterm-256color}"
mkdir -p "$HOME/projects"
cd "$HOME/projects"
# Explicit PATH replaces `source ~/.bashrc`; no user rc file is executed.
exec "$HOME/.opencode/bin/opencode" "$@"
OPENCODE_ANDROID_guest_run_sh
cat > "$PREFIX/bin/opencode-android" <<'OPENCODE_ANDROID_LAUNCHER'
#!/data/data/com.termux/files/usr/bin/bash
exec bash "$HOME/.local/share/opencode-android/start.sh" "$@"
OPENCODE_ANDROID_LAUNCHER
chmod 700 "$PREFIX/bin/opencode-android" "$install_dir"/*.sh
printf '\nInstaller siap. Untuk membuka lagi, jalankan: opencode-android\n\n'
# Give the terminal directly to the interactive application even when the
# installer itself was read from a pipe.
if [ -t 1 ] && [ -r /dev/tty ]; then
    exec "$PREFIX/bin/opencode-android" </dev/tty
else
    printf 'Jalankan opencode-android di terminal interaktif untuk melanjutkan.\n'
fi
