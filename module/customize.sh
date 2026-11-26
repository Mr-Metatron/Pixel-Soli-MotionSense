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

mkdir -p "$MODPATH/state"

# Preserve ownership through upgrades or reinstalling before pending cleanup.
# A separately installed adapter stays user-owned.
owned=false
if [ -f "$MODPATH/state/adapter.owned" ] || [ -f "$OLD/state/adapter.owned" ] ||
   [ -f "$PENDING/state/adapter.owned" ] || ! pm path "$ADAPTER" </dev/null 2>/dev/null | grep -q '^package:'; then
  owned=true
fi

# Replace a v0.1 pending task before installing, so even a failed reinstall
# cannot leave an old task that restores shared settings on the next boot.
if [ -d "$PENDING" ]; then
  if [ -f "$PENDING/state/adapter.owned" ]; then
    mkdir -p "${PENDING_SCRIPT%/*}"
    cp "$MODPATH/cleanup-once.sh" "$PENDING_SCRIPT.tmp" && chmod 0700 "$PENDING_SCRIPT.tmp" &&
      mv -f "$PENDING_SCRIPT.tmp" "$PENDING_SCRIPT" || abort '! Could not replace pending adapter cleanup.'
    rm -rf "$PENDING/state/settings"
    rm -f "$PENDING/state/snapshot.complete" "$PENDING/settings-keys.txt"
  else
    rm -f "$PENDING_SCRIPT"
    rm -rf "$PENDING"
  fi
fi

set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/post-fs-data.sh" 0 0 0755
set_perm "$MODPATH/uninstall.sh" 0 0 0755
set_perm "$MODPATH/cleanup-once.sh" 0 0 0755
set_perm_recursive "$MODPATH/state" 0 0 0700 0600

# An update with a different certificate fails normally; never uninstall to bypass it.
# Binder passes standard FDs to system_server; keep module-private files on
# this side of the pipe, both for the APK input and the captured diagnostics.
apk_size=$(stat -c %s "$MODPATH/adapter/SoliAdapter.apk") || abort '! Could not read adapter APK size.'
install_rc=0
install_output=$(cat "$MODPATH/adapter/SoliAdapter.apk" | pm install --user 0 -r -S "$apk_size" - 2>&1) || install_rc=$?
printf '%s\n' "$install_output" > "$MODPATH/state/install.log"
[ "$install_rc" -eq 0 ] || {
  cat "$MODPATH/state/install.log"
  abort '! Adapter installation failed; see PackageManager output above.'
}
grep -q '^Success' "$MODPATH/state/install.log" || abort '! Package manager did not confirm installation.'
if [ "$owned" = true ]; then
  touch "$MODPATH/state/adapter.owned"
fi

# Cancel old cleanup only after installation succeeds. Discard v0.1 snapshots;
# gesture preferences and shared Doze settings are left as the user set them.
rm -f "$PENDING_SCRIPT"
rm -rf "$PENDING"
rm -rf "$MODPATH/state/settings"
rm -f "$MODPATH/state/snapshot.complete" "$MODPATH/state/secure.list" "$MODPATH/state/install.complete"
rm -f /data/adb/soli_motion-lifecycle.lock

# Recover an already present Oslo disabled by its availability-property receiver.
if pm path com.google.oslo </dev/null 2>/dev/null | grep -q '^package:'; then
  pm enable --user 0 com.google.oslo </dev/null >/dev/null 2>&1
fi
ui_print '- Adapter installed. Enable only SystemUI and Oslo in LSPosed.'
ui_print '- Reboot, then open Motion Sense and enable the desired gestures.'
ui_print '- Hardware behavior is awaiting device validation.'

