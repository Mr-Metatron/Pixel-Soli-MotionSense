#!/system/bin/sh
# Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0
MODDIR=${0%/*}
SOURCE=/system_ext/etc/selinux/system_ext_mac_permissions.xml
TARGET=$MODDIR/system/system_ext/etc/selinux/system_ext_mac_permissions.xml
mkdir -p "$MODDIR/state" "${TARGET%/*}"
chmod 0700 "$MODDIR/state"
rm -f "$TARGET" "$TARGET.tmp"

# Nova runs module post-fs-data scripts before system.prop loading and metamodule mount.
case "$(getprop ro.vendor.aware_available)" in
  true|1) rm -f "$MODDIR/system.prop" ;;
  *) printf '%s\n' 'ro.vendor.aware_available=true' > "$MODDIR/system.prop" ;;
esac

if [ ! -r "$SOURCE" ]; then
  printf '%s\n' 'Current ROM system_ext_mac_permissions.xml is missing; no identity file mounted.' > "$MODDIR/state/identity.log"
  exit 0
fi

# Use Android's XML parser, before Zygote and before Magic Mount-rs. No daemon.
if timeout 8 /system/bin/dalvikvm -cp "$MODDIR/tools/identity.jar" \
    io.github.mrmetatron.soli.identity.Main "$SOURCE" "$TARGET" "$MODDIR/project-cert.hex" \
    > "$MODDIR/state/identity.log" 2>&1; then
  label=$(ls -Zd "$SOURCE" | awk '{print $1}')
  case "$label" in
    u:object_r:*:s0) ;;
    *) rm -f "$TARGET"; printf '%s\n' 'Could not read original SELinux label; skipped identity mount.' >> "$MODDIR/state/identity.log"; exit 0 ;;
  esac
  chmod 0644 "$TARGET"
  chown 0:0 "$TARGET"
  if ! chcon "$label" "$TARGET"; then
    rm -f "$TARGET"
    printf '%s\n' 'Could not apply original SELinux label; skipped identity mount.' >> "$MODDIR/state/identity.log"
  fi
else
  rm -f "$TARGET" "$TARGET.tmp"
  printf '%s\n' 'Identity merge failed; original ROM file retained.' >> "$MODDIR/state/identity.log"
fi
chmod 0600 "$MODDIR/state/identity.log"

