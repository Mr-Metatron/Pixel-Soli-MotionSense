#!/system/bin/sh
# Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0

[ "$BOOTMODE" = true ] || abort '! Install from the running KernelSU manager.'
[ "$KSU" = true ] || abort '! This package requires KernelSU / SukiSU Nova.'
case "$(getprop ro.product.device)" in
  flame|coral) ;;
  *) abort '! This module is for Pixel 4 / Pixel 4 XL.' ;;
esac
[ "${API:-0}" -ge 34 ] || abort '! Android 14 or newer is required; target: LOS 24.'

ui_print '- Preparing Oslo, Settings and LSPosed adapter'
ADAPTER=io.github.mrmetatron.soli.adapter
OLD=/data/adb/modules/soli_motion
PENDING=/data/adb/soli_motion-uninstall
PENDING_SCRIPT=/data/adb/service.d/soli_motion-cleanup.sh

# The one-off uninstaller can run while the manager installs again. Serialize
# their PackageManager/settings writes; the lock is released with this shell.
command -v flock >/dev/null 2>&1 || abort '! KernelSU BusyBox flock is required.'
exec 9>/data/adb/soli_motion-lifecycle.lock
attempt=0
while ! flock -n 9; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 15 ] || abort '! Previous uninstall cleanup is finishing; retry shortly.'
  sleep 1
done
mkdir -p "$MODPATH/state"

# Keep the first pre-install snapshot through upgrades, including staged upgrades.
if [ "$OLD" != "$MODPATH" ] && [ -f "$OLD/state/snapshot.complete" ]; then
  cp -a "$OLD/state/." "$MODPATH/state/" || abort '! Could not preserve settings snapshot.'
fi
# A failed/unfinished uninstall still owns the original settings snapshot.
if [ ! -f "$MODPATH/state/snapshot.complete" ] && [ -f "$PENDING/state/snapshot.complete" ]; then
  cp -a "$PENDING/state/." "$MODPATH/state/" || abort '! Could not preserve pending cleanup snapshot.'
fi
if [ ! -f "$MODPATH/state/snapshot.complete" ]; then
  mkdir -p "$MODPATH/state/settings"
  settings --user 0 list secure > "$MODPATH/state/secure.list" || abort '! Could not read user settings.'
  while IFS= read -r key; do
    [ -n "$key" ] || continue
    case "$key" in *[!a-z_0-9]*) abort '! Invalid settings key.' ;; esac
    if grep -q "^${key}=" "$MODPATH/state/secure.list"; then
      settings --user 0 get secure "$key" > "$MODPATH/state/settings/$key" || abort '! Could not save settings.'
    else
      touch "$MODPATH/state/settings/$key.absent"
    fi
  done < "$MODPATH/settings-keys.txt"
  rm -f "$MODPATH/state/secure.list"
  if ! pm path "$ADAPTER" 2>/dev/null | grep -q '^package:'; then
    touch "$MODPATH/state/adapter.owned"
  fi
  touch "$MODPATH/state/snapshot.complete"
fi

# system.prop is also refreshed before mount on each boot, including after OTA.
case "$(getprop ro.vendor.aware_available)" in
  true|1) rm -f "$MODPATH/system.prop" ;;
  *) printf '%s\n' 'ro.vendor.aware_available=true' > "$MODPATH/system.prop" ;;
esac

set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/post-fs-data.sh" 0 0 0755
set_perm "$MODPATH/uninstall.sh" 0 0 0755
set_perm "$MODPATH/cleanup-once.sh" 0 0 0755
set_perm_recursive "$MODPATH/state" 0 0 0700 0600

# An update with a different certificate fails normally; never uninstall to bypass it.
rm -f "$MODPATH/state/install.complete"
pm install --user 0 -r "$MODPATH/adapter/SoliAdapter.apk" > "$MODPATH/state/install.log" 2>&1 || {
  cat "$MODPATH/state/install.log"
  abort '! Adapter installation failed; keep the same project signing key.'
}
grep -q '^Success' "$MODPATH/state/install.log" || abort '! Package manager did not confirm installation.'
touch "$MODPATH/state/install.complete"

# Cancel old cleanup only after the new adapter and snapshot are in place.
rm -f "$PENDING_SCRIPT"
rm -rf "$PENDING"

# Recover an already present Oslo disabled by its availability-property receiver.
if pm path com.google.oslo 2>/dev/null | grep -q '^package:'; then
  pm enable --user 0 com.google.oslo >/dev/null 2>&1
fi
ui_print '- Adapter installed. Enable only SystemUI and Oslo in LSPosed.'
ui_print '- Reboot, then open Motion Sense and enable the desired gestures.'
ui_print '- Hardware behavior is awaiting device validation.'

