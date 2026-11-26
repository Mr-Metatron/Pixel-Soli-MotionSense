#!/system/bin/sh
# Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0
MODDIR=${0%/*}
MARKER=$MODDIR/state/oslo-permissions.granted
OSLO=com.google.oslo
umask 077

mkdir -p "$MODDIR/state"
chmod 0700 "$MODDIR/state"

# One read-only snapshot per boot; absence of an Oslo process may simply mean
# it has not started. Do this even after the one-time permission grant completed.
{
  if awk -f "$MODDIR/oslo-domain.awk" /vendor/etc/selinux/vendor_seapp_contexts 2>/dev/null; then
    printf '%s\n' 'oslo_domain_rule=present'
  else
    printf '%s\n' 'oslo_domain_rule=missing_or_incompatible'
  fi
  target=$MODDIR/system/system_ext/etc/selinux/system_ext_mac_permissions.xml
  if [ ! -s "$target" ]; then
    printf '%s\n' 'identity_file=not_prepared'
  elif cmp -s "$target" /system_ext/etc/selinux/system_ext_mac_permissions.xml; then
    printf '%s\n' 'identity_file=matches_visible_file'
  else
    printf '%s\n' 'identity_file=differs_from_visible_file'
  fi
  if processes=$(timeout 5 ps -AZ 2>/dev/null); then
    printf '%s\n' "$processes" | awk '
      $NF == "com.google.oslo" || index($NF, "com.google.oslo:") == 1 {
        found = 1
        status = ($1 ~ /^u:r:oslo_app:/) ? "expected" : "unexpected"
        printf "oslo_process=%s context=%s domain=%s\n", $NF, $1, status
      }
      END { if (!found) print "oslo_process=not_running (may not have started yet)" }
    '
  else
    printf '%s\n' 'oslo_process=query_failed'
  fi
  if [ -f "$MODDIR/state/identity.log" ]; then
    printf '%s\n' 'identity_merge_log:'
    tail -n 5 "$MODDIR/state/identity.log"
  fi
} > "$MODDIR/state/health.log.tmp"
chmod 0600 "$MODDIR/state/health.log.tmp"
mv -f "$MODDIR/state/health.log.tmp" "$MODDIR/state/health.log"

# default-permissions-soli.xml only runs on fresh user creation. On existing
# installations, grant Oslo's required runtime permission once after first mount
# so SoundTriggerManager in OsloGestureTrigger can attach; subsequent boots
# respect any later user revocation.
[ -f "$MARKER" ] && exit 0

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
