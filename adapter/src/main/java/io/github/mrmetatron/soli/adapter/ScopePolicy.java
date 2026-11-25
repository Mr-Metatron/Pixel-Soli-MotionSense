/* SPDX-License-Identifier: Apache-2.0 */
package io.github.mrmetatron.soli.adapter;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.Set;

/** Pure policy kept separate from Android hooks so its boundaries can be tested. */
final class ScopePolicy {
    static final String SYSTEM_UI = "com.android.systemui";
    static final String OSLO = "com.google.oslo";
    static final String SETTINGS = "org.hecker.floral.motionsense";
    static final String PLUGIN_PERMISSION = "com.android.systemui.permission.PLUGIN";
    static final String ALLOWLIST_RESOURCE = "com.android.systemui:array/config_pluginAllowlist";
    static final String CLOCK_SEND_PERMISSION = "com.android.systemui.permission.SEND_ALERT_BROADCASTS";
    private static final Set<String> SETTINGS_KEYS = Set.of(
            "aware_enabled", "skip_gesture", "tap_gesture", "silence_gesture",
            "skip_gesture_direction");

    private ScopePolicy() {}

    static boolean isTargetMainProcess(String packageName, String processName) {
        return (SYSTEM_UI.equals(packageName) || OSLO.equals(packageName))
                && packageName.equals(processName);
    }

    static boolean isPluginPermission(String permission, String packageName) {
        return PLUGIN_PERMISSION.equals(permission) && OSLO.equals(packageName);
    }

    static String[] appendOslo(String[] original) {
        if (Arrays.asList(original).contains(OSLO)) {
            return original;
        }
        String[] result = Arrays.copyOf(original, original.length + 1);
        result[original.length] = OSLO;
        return result;
    }

    static boolean isSpecialUser(int userId) {
        // UserHandle.USER_ALL and USER_CURRENT only; USER_CURRENT_OR_SELF is not used by Oslo.
        return userId == -1 || userId == -2;
    }

    static int localUserId(int requestedUserId, int actualUserId) {
        return isSpecialUser(requestedUserId) ? actualUserId : requestedUserId;
    }

    static boolean isOsloSetting(String key) {
        return key != null && SETTINGS_KEYS.contains(key);
    }

    static boolean isClockCommand(String action) {
        return "android.intent.action.SNOOZE_ALARM".equals(action)
                || "android.intent.action.DISMISS_TIMER".equals(action);
    }

    static boolean isSettingsUid(int callerUid, int settingsUid, String[] uidPackages) {
        // The Settings APK has no sharedUserId. Ambiguous shared identities keep the stock check.
        return callerUid == settingsUid && uidPackages != null && uidPackages.length == 1
                && SETTINGS.equals(uidPackages[0]);
    }

    static boolean matchesCertificate(byte[][] currentSigners, String expectedSha256) {
        if (currentSigners == null || currentSigners.length != 1
                || currentSigners[0] == null || expectedSha256 == null
                || !expectedSha256.matches("(?i)[0-9a-f]{64}")) {
            return false;
        }
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(currentSigners[0]);
            byte[] expected = new byte[digest.length];
            for (int i = 0; i < expected.length; i++) {
                expected[i] = (byte) Integer.parseInt(expectedSha256.substring(i * 2, i * 2 + 2), 16);
            }
            return MessageDigest.isEqual(digest, expected);
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 is required by Java", impossible);
        }
    }
}
