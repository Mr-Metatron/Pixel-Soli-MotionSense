#!/usr/bin/env python3
"""Create the sole distributable ZIP with stable ordering and complete build metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--cert-sha256', required=True)
args = parser.parse_args()
props = dict(line.split('=', 1) for line in (root / 'gradle.properties').read_text().splitlines()
             if '=' in line and not line.startswith('#'))
version = props['soliVersionName']
if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?', version):
    raise SystemExit('Invalid module version')
if not re.fullmatch(r'[0-9a-f]{64}', args.cert_sha256):
    raise SystemExit('Expected SHA256 signing certificate digest')
stage = root / '.build/module'
module_prop = (stage / 'module.prop').read_text().replace('@VERSION@', version).replace('@VERSION_CODE@', props['soliVersionCode'])
(stage / 'module.prop').write_text(module_prop)
for name in ('LICENSE', 'NOTICE', 'README.md'):
    shutil.copy2(root / name, stage / name)
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip())
metadata = {
    'version': version,
    'versionCode': int(props['soliVersionCode']),
    'sourceCommit': commit,
    'sourceDirty': dirty,
    'certificateSha256': args.cert_sha256,
    'osloInputSha256': '5f6c2e0c908e4d726eb62543c8d7f8492ade99b1d9043baa415873093598ac54',
    'deviceValidation': 'pending',
    'apkSha256': {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(stage.rglob('*.apk'))},
}
(stage / 'build-info.json').write_text(json.dumps(metadata, indent=2) + '\n')
epoch = int(subprocess.check_output(['git', 'show', '-s', '--format=%ct', 'HEAD'], cwd=root, text=True))
date = time.gmtime(max(epoch, 315532800))[:6]
dist = root / 'dist'
dist.mkdir(exist_ok=True)
for stale in dist.glob('soli_motion-*.zip'):
    stale.unlink()
output = dist / f'soli_motion-{version}.zip'
with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(stage.rglob('*')):
        if not path.is_file():
            continue
        relative = str(path.relative_to(stage))
        info = zipfile.ZipInfo(relative, date)
        info.create_system = 3
        info.external_attr = (0o100755 if path.suffix == '.sh' else 0o100644) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, path.read_bytes())
digest = hashlib.sha256(output.read_bytes()).hexdigest()
(root / '.build/release-notes.md').write_text(f'''## Pixel Soli Motion Sense {version}

单一 KSU 模块包，包含固定版 Oslo、原版 Motion Sense Settings、局部 LSPosed 适配及 Doze RRO。

在 Nova 管理器刷入 ZIP 后，在 LSPosed 中仅启用 **SystemUI** 和 **Oslo**，完整重启，再打开 Motion Sense 设置。

**状态：已完成自动构建与静态验证，待实机验证。** 手势、glow、Air DJ、Clock、来电、Doze、人脸及 OTA 的实际效果见仓库验证说明。

源码提交：`{commit}`

SHA256：`{digest}`

签名证书 SHA256：`{args.cert_sha256}`

下载下方唯一的 `soli_motion-{version}.zip`，无需单独安装 APK。
''')
print(f'{output.name}: {output.stat().st_size:,} bytes; SHA256 {digest}')
