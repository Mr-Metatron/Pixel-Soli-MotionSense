#!/usr/bin/env python3
"""Verify the installed layout, signing identity, unchanged upstream payload and stub exclusion."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'adapter/SoliAdapter.apk': 'io.github.mrmetatron.soli.adapter',
    'system/system_ext/priv-app/OsloFeedback/OsloFeedback.apk': 'com.google.oslo',
    'system/system_ext/priv-app/MotionSenseSettings/MotionSenseSettings.apk': 'org.hecker.floral.motionsense',
    'system/system_ext/overlay/SoliDoze.apk': 'org.metatron.soli.overlay.doze',
}


def defined_classes(dex):
    """Read DEX class definitions, rather than mistaking normal API references for bundled stubs."""
    assert dex[:4] == b'dex\n', 'Expected standard DEX'
    strings_offset = struct.unpack_from('<I', dex, 60)[0]
    types_offset = struct.unpack_from('<I', dex, 68)[0]
    count, offset = struct.unpack_from('<II', dex, 96)
    for index in range(count):
        type_index = struct.unpack_from('<I', dex, offset + 32 * index)[0]
        string_index = struct.unpack_from('<I', dex, types_offset + 4 * type_index)[0]
        position = struct.unpack_from('<I', dex, strings_offset + 4 * string_index)[0]
        while dex[position] & 0x80:
            position += 1
        position += 1
        yield dex[position:dex.index(0, position)].decode('utf-8')


def verify(path):
    sdk = Path(os.environ.get('ANDROID_HOME') or os.environ['ANDROID_SDK_ROOT'])
    bt = sdk / 'build-tools/35.0.0'
    with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory() as temporary:
        names = archive.namelist()
        assert len(names) == len(set(names)), 'Duplicate ZIP entries'
        assert all(not n.startswith('/') and '..' not in Path(n).parts for n in names), 'Unsafe ZIP path'
        assert set(n for n in names if n.endswith('.apk')) == set(EXPECTED), 'Unexpected app layout'
        assert not any(n.endswith(('.p12', '.pem', '.pk8', '.base64')) for n in names), 'Signing key in module'
        assert 'service.sh' not in names and 'update.json' not in names, 'Unexpected persistent service/update feed'
        assert 'system/system_ext/etc/selinux/system_ext_mac_permissions.xml' not in names, 'Must merge current ROM at boot'
        assert 'id=soli_motion\n' in archive.read('module.prop').decode(), 'Wrong module identity'
        for script in ('customize.sh', 'post-fs-data.sh', 'boot-completed.sh', 'uninstall.sh', 'cleanup-once.sh'):
            assert archive.getinfo(script).external_attr >> 16 & 0o111, f'Not executable: {script}'
        sepolicy_lines = [line.strip() for line in archive.read('sepolicy.rule').decode().splitlines()
                          if line.strip() and not line.strip().startswith('#')]
        assert sepolicy_lines == [
            'allow priv_app_36 vendor_aware_available_prop file { read getattr map open }'
        ], f'Unexpected sepolicy.rule content: {sepolicy_lines}'
        for name in names:
            if name.endswith('.xml'):
                ET.fromstring(archive.read(name))
        metadata = json.loads(archive.read('build-info.json'))
        cert_hex = archive.read('project-cert.hex').decode().strip()
        assert hashlib.sha256(bytes.fromhex(cert_hex)).hexdigest() == metadata['certificateSha256']
        for name, package in EXPECTED.items():
            data = archive.read(name)
            assert hashlib.sha256(data).hexdigest() == metadata['apkSha256'][name]
            apk = Path(temporary) / Path(name).name
            apk.write_bytes(data)
            output = subprocess.check_output([str(bt / 'apksigner'), 'verify', '--print-certs', str(apk)], text=True)
            digest = re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)', output).group(1)
            assert digest == metadata['certificateSha256'], f'Unexpected signer: {name}'
            badging = subprocess.check_output([str(bt / 'aapt2'), 'dump', 'badging', str(apk)], text=True)
            assert f"package: name='{package}'" in badging, f'Wrong package: {name}'
            if package == 'org.hecker.floral.motionsense':
                manifest = subprocess.check_output([str(bt / 'aapt2'), 'dump', 'xmltree', '--file', 'AndroidManifest.xml', str(apk)], text=True)
                assert 'sharedUserId' not in manifest, 'Settings must have an independent UID'
                assert 'usesNonSdkApi' in manifest, 'Missing scoped hidden API flag'
                assert 'com.android.systemui.permission.SEND_ALERT_BROADCASTS' in manifest
            with zipfile.ZipFile(io.BytesIO(data)) as app:
                if package != 'com.google.oslo':
                    for entry in app.namelist():
                        if re.fullmatch(r'classes\d*\.dex', entry):
                            classes = list(defined_classes(app.read(entry)))
                            # AndroidX retains real android/support/v4 compatibility classes.
                            assert not any(c.startswith('Landroid/') and not c.startswith('Landroid/support/')
                                           for c in classes), 'Framework stub shipped as runtime code'
                            assert not any(c.startswith('Lde/robv/android/xposed/') for c in classes), 'Xposed API implementation shipped'
                else:
                    with zipfile.ZipFile(ROOT / '.build/downloads/OsloFeedback.apk') as original:
                        for entry in original.namelist():
                            if not entry.startswith('META-INF/'):
                                assert app.read(entry) == original.read(entry), f'Upstream Oslo content changed: {entry}'
        with zipfile.ZipFile(io.BytesIO(archive.read('tools/identity.jar'))) as helper:
            assert set(helper.namelist()) == {'classes.dex'}
    print('Package verified: four APKs, one signer, original Oslo payload, no runtime stubs, no static ROM identity file.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: verify-package.py MODULE_ZIP')
    verify(Path(sys.argv[1]))
