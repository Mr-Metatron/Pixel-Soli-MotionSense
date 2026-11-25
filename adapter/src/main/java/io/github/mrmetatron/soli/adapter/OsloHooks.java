/* SPDX-License-Identifier: Apache-2.0 */
package io.github.mrmetatron.soli.adapter;

import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.media.session.MediaSessionManager;
import android.os.Binder;
import android.os.Bundle;
import android.os.Handler;
import android.os.Process;
import android.os.UserHandle;
import android.provider.Settings;

import java.util.concurrent.Executor;

import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedHelpers;

final class OsloHooks {
    private OsloHooks() {}

    static void install(ClassLoader classLoader) {
        installServicePermission(classLoader);
        try {
            UserHandle localUser = Process.myUserHandle();
            int localUserId = (Integer) XposedHelpers.callMethod(localUser, "getIdentifier");
            installMedia(localUser);
            installClock(localUser);
            installSettings(localUserId);
        } catch (Throwable error) {
            HookLog.failure("read Oslo process user", error);
        }
    }

    private static void installServicePermission(ClassLoader classLoader) {
        try {
            XposedHelpers.findAndHookMethod("com.google.oslo.service.OsloService", classLoader,
                    "checkPermission", new XC_MethodHook() {
                        @Override
                        protected void beforeHookedMethod(MethodHookParam param) {
                            int callerUid = Binder.getCallingUid();
                            if (callerUid == Process.myUid()) {
                                // This is a void enforcement point, not a permission-value query.
                                param.setResult(null);
                                return;
                            }
                            try {
                                PackageManager pm = ((Context) param.thisObject).getPackageManager();
                                String[] packages = pm.getPackagesForUid(callerUid);
                                if (packages == null || packages.length != 1
                                        || !ScopePolicy.SETTINGS.equals(packages[0])) {
                                    return;
                                }
                                // Re-read this small, infrequent Binder-client check so uninstall/reinstall
                                // cannot inherit a cached allow decision for a recycled UID.
                                PackageInfo info = ProjectIdentity.signedPackage(pm, ScopePolicy.SETTINGS);
                                if (info != null && info.applicationInfo != null
                                        && ScopePolicy.isSettingsUid(callerUid, info.applicationInfo.uid, packages)) {
                                    param.setResult(null);
                                    HookLog.once("OsloService accepted project-signed Settings UID");
                                }
                            } catch (PackageManager.NameNotFoundException | RuntimeException error) {
                                HookLog.failure("OsloService caller lookup", error);
                            }
                            // Other UIDs execute the original STATUS_BAR_SERVICE enforcement.
                            // Binder identity is never cleared or replaced.
                        }
                    });
        } catch (Throwable error) {
            HookLog.failure("install OsloService.checkPermission", error);
        }
    }

    private static void installMedia(UserHandle localUser) {
        hook(MediaSessionManager.class, "getActiveSessionsForUser", ComponentName.class,
                UserHandle.class, userArgument(1, localUser));
        hook(MediaSessionManager.class, "addOnActiveSessionsChangedListener", ComponentName.class,
                UserHandle.class, Executor.class, MediaSessionManager.OnActiveSessionsChangedListener.class,
                userArgument(1, localUser));
    }

    private static void installClock(UserHandle localUser) {
        hook(ContextWrapper.class, "registerReceiverAsUser", BroadcastReceiver.class, UserHandle.class,
                IntentFilter.class, String.class, Handler.class, new XC_MethodHook() {
                    @Override
                    protected void beforeHookedMethod(MethodHookParam param) {
                        if (ScopePolicy.CLOCK_SEND_PERMISSION.equals(param.args[3])) {
                            replaceSpecialUser(param, 1, localUser);
                        }
                    }
                });
        hook(ContextWrapper.class, "startActivityAsUser", Intent.class, Bundle.class, UserHandle.class,
                new XC_MethodHook() {
                    @Override
                    protected void beforeHookedMethod(MethodHookParam param) {
                        Intent intent = (Intent) param.args[0];
                        if (intent != null && ScopePolicy.isClockCommand(intent.getAction())) {
                            replaceSpecialUser(param, 2, localUser);
                        }
                    }
                });
    }

    private static void installSettings(int localUserId) {
        hook(Settings.Secure.class, "getIntForUser", ContentResolver.class, String.class,
                int.class, int.class, new XC_MethodHook() {
                    @Override
                    protected void beforeHookedMethod(MethodHookParam param) {
                        if (ScopePolicy.isOsloSetting((String) param.args[1])) {
                            param.args[3] = ScopePolicy.localUserId((Integer) param.args[3], localUserId);
                        }
                    }
                });
    }

    private static XC_MethodHook userArgument(int index, UserHandle localUser) {
        return new XC_MethodHook() {
            @Override
            protected void beforeHookedMethod(MethodHookParam param) {
                replaceSpecialUser(param, index, localUser);
            }
        };
    }

    private static void replaceSpecialUser(XC_MethodHook.MethodHookParam param, int index,
            UserHandle localUser) {
        Object requested = param.args[index];
        if (requested instanceof UserHandle) {
            try {
                int userId = (Integer) XposedHelpers.callMethod(requested, "getIdentifier");
                if (ScopePolicy.isSpecialUser(userId)) {
                    param.args[index] = localUser;
                }
            } catch (RuntimeException error) {
                HookLog.failure("Oslo user argument", error);
            }
        }
    }

    private static void hook(Class<?> owner, String method, Object... signatureAndCallback) {
        try {
            XposedHelpers.findAndHookMethod(owner, method, signatureAndCallback);
        } catch (Throwable error) {
            HookLog.failure("install " + owner.getSimpleName() + "." + method, error);
        }
    }
}
