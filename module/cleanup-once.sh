#!/system/bin/sh
# Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0
PENDING=/data/adb/soli_motion-uninstall
SCRIPT=/data/adb/service.d/soli_motion-cleanup.sh
ADAPTER=io.github.mrmetatron.soli.adapter
umask 077

# This file is copied into service.d only when uninstalling, then removes itself.
[ -d "$PENDING" ] || { rm -f "$SCRIPT"; exit 0; }
exec > "$PENDING/cleanup.log" 2>&1

attempt=0
while [ "$(getprop sys.boot_completed)" != 1 ]; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 120 ]; then
    printf '%s\n' 'Boot did not complete within 120 seconds; cleanup will retry next boot.'
    exit 0
  fi
  sleep 1
done

# A concurrent reinstall takes the same lock before inheriting the snapshot.
exec 9>/data/adb/soli_motion-lifecycle.lock
flock -n 9 || { printf '%s\n' 'Module installation is active; cleanup deferred.'; exit 0; }
for module in /data/adb/modules/soli_motion /data/adb/modules_update/soli_motion; do
  if [ -f "$module/module.prop" ] && [ -f "$module/state/install.complete" ] && [ ! -f "$module/remove" ]; then
    printf '%s\n' 'Module is installed again; its saved snapshot owns future cleanup.'
    if [ -f "$module/state/snapshot.complete" ]; then
      rm -f "$SCRIPT"
      rm -rf "$PENDING"
    fi
    exit 0
  fi
done

ok=true
if [ -f "$PENDING/state/snapshot.complete" ] && [ -r "$PENDING/settings-keys.txt" ]; then
  while IFS= read -r key; do
    [ -n "$key" ] || continue
    case "$key" in *[!a-z_0-9]*) ok=false; continue ;; esac
    if [ -f "$PENDING/state/settings/$key.absent" ]; then
      timeout 10 settings --user 0 delete secure "$key" >/dev/null 2>&1 || ok=false
    elif [ -f "$PENDING/state/settings/$key" ]; then
      timeout 10 settings --user 0 put secure "$key" "$(cat "$PENDING/state/settings/$key")" >/dev/null 2>&1 || ok=false
    else
      printf 'Missing snapshot for %s; cleanup retained.\n' "$key"
      ok=false
    fi
  done < "$PENDING/settings-keys.txt"
else
  printf '%s\n' 'Settings snapshot is incomplete; cleanup retained.'
  ok=false
fi

if [ -f "$PENDING/state/adapter.owned" ]; then
  if timeout 10 pm list packages --user 0 "$ADAPTER" > "$PENDING/packages.list" 2>/dev/null; then
    if grep -qx "package:$ADAPTER" "$PENDING/packages.list"; then
      timeout 10 pm uninstall --user 0 "$ADAPTER" > "$PENDING/uninstall.log" 2>&1 || ok=false
      grep -q '^Success' "$PENDING/uninstall.log" || ok=false
    fi
    rm -f "$PENDING/packages.list"
  else
    ok=false
  fi
fi

if [ "$ok" = true ]; then
  rm -f "$SCRIPT"
  rm -rf "$PENDING"
else
  printf '%s\n' 'One or more restoration commands failed; snapshot retained for the next boot.'
fi
