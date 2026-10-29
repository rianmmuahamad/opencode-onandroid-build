# OpenCode Android: invoked only for interactive login shells with a terminal.
# Recovery: OPENCODE_ANDROID_SHELL_ONLY=1 bash -l
case $- in
    *i*)
        if [ -t 0 ] && [ -t 1 ] && [ "${OPENCODE_ANDROID_SHELL_ONLY:-0}" != 1 ]; then
            OPENCODE_ANDROID_SHELL_ONLY=1 "$PREFIX/bin/bash" \
                "$PREFIX/libexec/opencode-android/start.sh"
        fi
        ;;
esac
