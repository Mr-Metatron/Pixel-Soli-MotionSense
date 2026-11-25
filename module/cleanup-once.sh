#!/system/bin/sh
# Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0
PENDING=/data/adb/soli_motion-uninstall
SCRIPT=/data/adb/service.d/soli_motion-cleanup.sh
ADAPTER=io.github.mrmetatron.soli.adapter
umask 077

# This file is copied into service.d only when uninstalling, then removes itself.
[ -f "$PENDING/state/adapter.owned" ] || { rm -f "$SCRIPT"; rm -rf "$PENDING"; exit 0; }
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

# A successful reinstall inherits ownership and cancels this pending uninstall.
for module in /data/adb/modules/soli_motion /data/adb/modules_update/soli_motion; do
  if [ -f "$module/module.prop" ] && [ -f "$module/state/adapter.owned" ] && [ ! -f "$module/remove" ]; then
    printf '%s\n' 'Module is installed again; adapter retained.'
    rm -f "$SCRIPT"
    rm -rf "$PENDING"
    exit 0
  fi
done

if ! timeout 10 pm list packages --user 0 "$ADAPTER" > "$PENDING/packages.list" 2>/dev/null; then
  printf '%s\n' 'Could not query PackageManager; cleanup will retry next boot.'
  exit 0
fi
if grep -qx "package:$ADAPTER" "$PENDING/packages.list"; then
  # A reinstall may have cancelled cleanup while PackageManager was queried.
  [ -f "$PENDING/state/adapter.owned" ] || exit 0
  if ! timeout 10 pm uninstall --user 0 "$ADAPTER" > "$PENDING/uninstall.log" 2>&1 ||
     ! grep -q '^Success' "$PENDING/uninstall.log"; then
    printf '%s\n' 'Adapter removal failed; cleanup will retry next boot.'
    exit 0
  fi
fi
rm -f "$SCRIPT"
rm -rf "$PENDING"
