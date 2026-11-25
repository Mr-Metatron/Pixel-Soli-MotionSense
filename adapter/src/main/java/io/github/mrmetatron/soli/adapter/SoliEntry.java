/* SPDX-License-Identifier: Apache-2.0 */
package io.github.mrmetatron.soli.adapter;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

/** Installed from handleLoadPackage, before the target Application is initialized. */
public final class SoliEntry implements IXposedHookLoadPackage {
    @Override
    public void handleLoadPackage(XC_LoadPackage.LoadPackageParam loadedPackage) {
        if (!ScopePolicy.isTargetMainProcess(loadedPackage.packageName, loadedPackage.processName)
                || !loadedPackage.isFirstApplication) {
            return;
        }
        if (ScopePolicy.SYSTEM_UI.equals(loadedPackage.packageName)) {
            SystemUiHooks.install(loadedPackage.classLoader);
        } else {
            OsloHooks.install(loadedPackage.classLoader);
        }
    }
}
