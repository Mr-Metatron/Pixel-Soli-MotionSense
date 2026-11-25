#!/usr/bin/env bash
# Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."

SDK=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}
[[ -n "$SDK" ]] || { echo 'Set ANDROID_HOME to an Android SDK.' >&2; exit 1; }
BT="$SDK/build-tools/35.0.0"
for command in java javac keytool curl python3; do command -v "$command" >/dev/null; done
[[ -x "$BT/apksigner" && -x "$BT/d8" ]] || { echo 'Install build-tools;35.0.0.' >&2; exit 1; }
mkdir -p .build/signing .build/downloads .build/identity/classes dist
chmod 0700 .build/signing

# One fixed project key for every APK; an optional single secret replaces the whole PKCS12.
if [[ -n ${SOLI_SIGNING_KEY:-} ]]; then
  printf '%s' "$SOLI_SIGNING_KEY" | base64 --decode > .build/signing/project.p12
else
  base64 --decode signing/default.p12.base64 > .build/signing/project.p12
fi
chmod 0600 .build/signing/project.p12
keytool -exportcert -alias soli -keystore .build/signing/project.p12 -storepass soli_motion \
  -file .build/signing/cert.der >/dev/null
CERT_SHA256=$(sha256sum .build/signing/cert.der | cut -d' ' -f1)
python3 - <<'PY'
from pathlib import Path
Path('.build/signing/cert.hex').write_text(Path('.build/signing/cert.der').read_bytes().hex() + '\n')
PY

# The sole external app input. Keep its DEX/resources unchanged and only re-sign it.
OSLO=.build/downloads/OsloFeedback.apk
if [[ ! -f "$OSLO" ]] || ! printf '%s  %s\n' '5f6c2e0c908e4d726eb62543c8d7f8492ade99b1d9043baa415873093598ac54' "$OSLO" | sha256sum -c --status; then
  curl --fail --silent --show-error --location --retry 3 \
    'https://raw.githubusercontent.com/its-hecker/infinity_cnb_proprietary_vendor_google_coral/211e454a5809b98fb85e883ace545fbdb9ba939d/proprietary/system_ext/priv-app/OsloFeedback/OsloFeedback.apk' \
    -o "$OSLO"
fi
printf '%s  %s\n' '5f6c2e0c908e4d726eb62543c8d7f8492ade99b1d9043baa415873093598ac54' "$OSLO" | sha256sum -c

./gradlew --no-daemon --max-workers="${GRADLE_WORKERS:-$(nproc)}" \
  -PsoliCertSha256="$CERT_SHA256" \
  :adapter:assembleRelease :adapter:testReleaseUnitTest :settings:assembleRelease :doze-overlay:assembleRelease

# A tiny pre-mount helper uses platform XML APIs and has no packaged runtime dependencies.
javac --release 8 -d .build/identity/classes tools/identity/src/io/github/mrmetatron/soli/identity/Main.java
javac -cp .build/identity/classes -d .build/identity/classes tools/identity/tests/io/github/mrmetatron/soli/identity/MainTest.java
java -cp .build/identity/classes io.github.mrmetatron.soli.identity.MainTest
jar cf .build/identity/helper.jar -C .build/identity/classes io/github/mrmetatron/soli/identity/Main.class
mkdir -p .build/identity/dex
"$BT/d8" --release --min-api 34 --lib "$SDK/platforms/android-36/android.jar" \
  --output .build/identity/dex .build/identity/helper.jar

python3 -m unittest discover -s tests -v
python3 settings/tests/check-lottie-assets.py
mkdir -p .build/lab-tests
javac -d .build/lab-tests settings/src/org/hecker/floral/motionsense/motionsense/lab/LabEngine.java settings/tests/LabEngineTest.java
java -cp .build/lab-tests org.hecker.floral.motionsense.motionsense.lab.LabEngineTest

rm -rf .build/module
cp -a module .build/module
mkdir -p .build/module/adapter .build/module/tools .build/module/system/system_ext/priv-app/{OsloFeedback,MotionSenseSettings} \
  .build/module/system/system_ext/overlay
cp .build/signing/cert.hex .build/module/project-cert.hex
(cd .build/identity/dex && zip -q -X "$OLDPWD/.build/module/tools/identity.jar" classes.dex)

sign_apk() {
  local input=$1 output=$2 aligned
  aligned=".build/$(basename "$output").aligned.apk"
  "$BT/zipalign" -P 16 -f 4 "$input" "$aligned"
  "$BT/apksigner" sign --ks .build/signing/project.p12 --ks-key-alias soli \
    --ks-pass pass:soli_motion --key-pass pass:soli_motion \
    --v4-signing-enabled false --out "$output" "$aligned"
  "$BT/apksigner" verify --verbose "$output"
}
sign_apk "$OSLO" .build/module/system/system_ext/priv-app/OsloFeedback/OsloFeedback.apk
sign_apk adapter/build/outputs/apk/release/adapter-release-unsigned.apk .build/module/adapter/SoliAdapter.apk
sign_apk settings/build/outputs/apk/release/settings-release-unsigned.apk .build/module/system/system_ext/priv-app/MotionSenseSettings/MotionSenseSettings.apk
sign_apk doze-overlay/build/outputs/apk/release/doze-overlay-release-unsigned.apk .build/module/system/system_ext/overlay/SoliDoze.apk

python3 scripts/package.py --cert-sha256 "$CERT_SHA256"
python3 scripts/verify-package.py dist/soli_motion-*.zip
sha256sum dist/soli_motion-*.zip
