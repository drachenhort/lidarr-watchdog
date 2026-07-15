#!/bin/sh
set -e

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

if [ "$(id -g watchdog)" != "$PGID" ]; then
    groupmod -o -g "$PGID" watchdog
fi
if [ "$(id -u watchdog)" != "$PUID" ]; then
    usermod -o -u "$PUID" watchdog
fi

chown -R watchdog:watchdog /config

exec gosu watchdog "$@"
