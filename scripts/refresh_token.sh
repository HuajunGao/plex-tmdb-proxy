#!/bin/bash
# Reads the current Plex token from Preferences.xml and updates /etc/plex-sync.env
set -e

PREFS="/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml"
ENV_FILE="/etc/plex-sync.env"

TOKEN=$(grep -oP 'PlexOnlineToken="\K[^"]+' "$PREFS")

if [[ -z "$TOKEN" ]]; then
    echo "$(date): ERROR - could not read token from Preferences.xml" >&2
    exit 1
fi

echo "PLEX_TOKEN=$TOKEN" > "$ENV_FILE"
chmod 600 "$ENV_FILE"
echo "$(date): token refreshed (${TOKEN:0:8}...)"
