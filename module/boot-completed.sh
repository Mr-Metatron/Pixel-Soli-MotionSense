#!/system/bin/sh
# Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0
MODDIR=${0%/*}
MARKER=$MODDIR/state/oslo-permissions.granted
OSLO=com.google.oslo
umask 077

# default-permissions-soli.xml only runs on fresh user creation. On existing
# installations, grant Oslo's required runtime permission once after first mount
# so SoundTriggerManager in OsloGestureTrigger can attach; subsequent boots
# respect any later user revocation.
[ -f "$MARKER" ] && exit 0
mkdir -p "$MODDIR/state"
chmod 0700 "$MODDIR/state"

# Keep stdin/stdout/stderr off module-private files because pm forwards them over Binder.
if ! oslo_path=$(timeout 10 pm path "$OSLO" </dev/null 2>&1); then
  exit 0
fi
printf '%s\n' "$oslo_path" | grep -q '^package:' || exit 0

grant_rc=0
grant_output=$(timeout 10 pm grant --user 0 "$OSLO" android.permission.RECORD_AUDIO </dev/null 2>&1) || grant_rc=$?
printf '%s\n' "$grant_output" > "$MODDIR/state/oslo-grant.log"
chmod 0600 "$MODDIR/state/oslo-grant.log"
[ "$grant_rc" -eq 0 ] || exit 0

# Best-effort notification grant; do not block readiness if unavailable.
timeout 10 pm grant --user 0 "$OSLO" android.permission.POST_NOTIFICATIONS </dev/null >/dev/null 2>&1 || true
touch "$MARKER"
chmod 0600 "$MARKER"
