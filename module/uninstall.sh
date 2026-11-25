#!/system/bin/sh
# Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0
MODDIR=${0%/*}
PENDING=/data/adb/soli_motion-uninstall
SCRIPT=/data/adb/service.d/soli_motion-cleanup.sh
umask 077

# Nova invokes this during post-fs-data, before PackageManager/SettingsProvider.
# Save only our snapshot and schedule a one-off late-start cleanup, then return.
[ -f "$MODDIR/state/snapshot.complete" ] || exit 0
mkdir -p "$PENDING/state" /data/adb/service.d || exit 1
cp -a "$MODDIR/state/settings" "$PENDING/state/" || exit 1
cp "$MODDIR/state/snapshot.complete" "$PENDING/state/" || exit 1
cp "$MODDIR/settings-keys.txt" "$PENDING/settings-keys.txt" || exit 1
if [ -f "$MODDIR/state/adapter.owned" ]; then
  cp "$MODDIR/state/adapter.owned" "$PENDING/state/" || exit 1
else
  rm -f "$PENDING/state/adapter.owned"
fi
cp "$MODDIR/cleanup-once.sh" "$SCRIPT.tmp" || exit 1
chmod 0700 "$PENDING" "$PENDING/state" "$SCRIPT.tmp"
mv -f "$SCRIPT.tmp" "$SCRIPT" || exit 1

