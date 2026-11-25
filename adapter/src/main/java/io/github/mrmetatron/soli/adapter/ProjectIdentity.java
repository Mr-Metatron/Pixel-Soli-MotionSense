/* SPDX-License-Identifier: Apache-2.0 */
package io.github.mrmetatron.soli.adapter;

import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;

final class ProjectIdentity {
    private ProjectIdentity() {}

    @SuppressWarnings("deprecation")
    static PackageInfo signedPackage(PackageManager packageManager, String packageName)
            throws PackageManager.NameNotFoundException {
        PackageInfo info = packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES);
        if (info.applicationInfo == null) {
            return null;
        }
        int flags = info.applicationInfo.flags;
        if (!ScopePolicy.isUnmodifiedSystemApp(
                (flags & ApplicationInfo.FLAG_SYSTEM) != 0,
                (flags & ApplicationInfo.FLAG_UPDATED_SYSTEM_APP) != 0)) {
            return null;
        }
        if (info.signingInfo == null) {
            return null;
        }
        Signature[] signatures = info.signingInfo.getApkContentsSigners();
        if (signatures == null || signatures.length != 1) {
            return null;
        }
        byte[][] bytes = {signatures[0].toByteArray()};
        return ScopePolicy.matchesCertificate(bytes, BuildConfig.SOLI_CERT_SHA256) ? info : null;
    }
}
