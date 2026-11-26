/* SPDX-License-Identifier: Apache-2.0 */
package io.github.mrmetatron.soli.adapter;

import android.content.ComponentName;
import android.content.pm.PackageManager;
import android.content.res.AssetManager;
import android.content.res.Resources;

import java.util.Map;
import java.util.WeakHashMap;

import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedHelpers;

final class SystemUiHooks {
    // The module and system APKs are updated together, followed by a full reboot.
    private static volatile Boolean osloCertificateMatches;
    // Plugin Resources can reuse SystemUI's numeric IDs. Keep lookups per asset set,
    // and resolve again when Resources switches to a different AssetManager.
    private static final Map<AssetManager, Integer> allowlistIds = new WeakHashMap<>();

    private SystemUiHooks() {}

    static void install(ClassLoader classLoader) {
        installAllowlist();
        installPluginPermission(classLoader);
        installLifecycleLog(classLoader);
    }

    private static void installAllowlist() {
        try {
            XposedHelpers.findAndHookMethod(Resources.class, "getStringArray", int.class,
                    new XC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) {
                            if (param.hasThrowable() || !(param.getResult() instanceof String[])) {
                                return;
                            }
                            try {
                                Resources resources = (Resources) param.thisObject;
                                int allowlistId;
                                synchronized (allowlistIds) {
                                    AssetManager assets = resources.getAssets();
                                    Integer cached = allowlistIds.get(assets);
                                    allowlistId = cached != null ? cached : resources.getIdentifier(
                                            ScopePolicy.ALLOWLIST_RESOURCE, null, null);
                                    // A missing resource may become available after assets are added.
                                    if (cached == null && allowlistId != 0) {
                                        allowlistIds.put(assets, allowlistId);
                                    }
                                }
                                if (allowlistId != 0 && allowlistId == (Integer) param.args[0]) {
                                    param.setResult(ScopePolicy.appendOslo((String[]) param.getResult()));
                                    HookLog.once("SystemUI config_pluginAllowlist matched");
                                }
                            } catch (RuntimeException error) {
                                HookLog.failure("SystemUI allowlist", error);
                            }
                        }
                    });
        } catch (Throwable error) {
            HookLog.failure("install Resources.getStringArray", error);
        }
    }

    private static void installPluginPermission(ClassLoader classLoader) {
        try {
            XposedHelpers.findAndHookMethod("android.app.ApplicationPackageManager", classLoader,
                    "checkPermission", String.class, String.class, new XC_MethodHook() {
                        @Override
                        protected void beforeHookedMethod(MethodHookParam param) {
                            if (!ScopePolicy.isPluginPermission((String) param.args[0], (String) param.args[1])) {
                                return;
                            }
                            try {
                                Boolean matches = osloCertificateMatches;
                                if (matches == null) {
                                    synchronized (SystemUiHooks.class) {
                                        matches = osloCertificateMatches;
                                        if (matches == null) {
                                            matches = ProjectIdentity.signedPackage(
                                                    (PackageManager) param.thisObject, ScopePolicy.OSLO) != null;
                                            osloCertificateMatches = matches;
                                        }
                                    }
                                }
                                if (matches) {
                                    param.setResult(PackageManager.PERMISSION_GRANTED);
                                    HookLog.once("SystemUI PLUGIN check matched project-signed Oslo");
                                } else {
                                    HookLog.once("SystemUI Oslo certificate mismatch; keeping stock PLUGIN check");
                                }
                            } catch (PackageManager.NameNotFoundException | RuntimeException error) {
                                // A transient lookup failure must not grant access or poison the cache.
                                HookLog.failure("SystemUI Oslo certificate lookup", error);
                            }
                        }
                    });
        } catch (Throwable error) {
            HookLog.failure("install ApplicationPackageManager.checkPermission", error);
        }
    }

    private static void installLifecycleLog(ClassLoader classLoader) {
        // Read-only observation of the frozen SystemUI PluginInstance implementation.
        // Its version, enabled-state and listener decisions are left intact.
        for (String method : new String[] {"onCreate", "loadPlugin"}) {
            try {
                XposedHelpers.findAndHookMethod("com.android.systemui.shared.plugins.PluginInstance",
                        classLoader, method, new XC_MethodHook() {
                            @Override
                            protected void afterHookedMethod(MethodHookParam param) {
                                try {
                                    ComponentName component = (ComponentName) XposedHelpers.callMethod(
                                            param.thisObject, "getComponentName");
                                    if (!ScopePolicy.OSLO.equals(component.getPackageName())) {
                                        return;
                                    }
                                    String name = component.getClassName();
                                    if (!"com.google.oslo.OsloOverlay".equals(name)
                                            && !"com.google.oslo.OsloSensorManager".equals(name)) {
                                        return;
                                    }
                                    if (param.hasThrowable()) {
                                        HookLog.failure(name + " " + method, param.getThrowable());
                                    } else {
                                        Object plugin = XposedHelpers.callMethod(param.thisObject, "getPlugin");
                                        HookLog.once(name + " " + method + ": "
                                                + (plugin != null ? "loaded" : "not loaded"));
                                    }
                                } catch (RuntimeException error) {
                                    HookLog.failure("read SystemUI plugin lifecycle", error);
                                }
                            }
                        });
            } catch (Throwable error) {
                HookLog.failure("install plugin lifecycle log " + method, error);
            }
        }
    }
}
