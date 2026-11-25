/* SPDX-License-Identifier: Apache-2.0 */
package io.github.mrmetatron.soli.adapter;

import static org.junit.Assert.*;

import java.nio.charset.StandardCharsets;
import org.junit.Test;

public final class ScopePolicyTest {
    private static final byte[] CERT_FIXTURE = "abc".getBytes(StandardCharsets.UTF_8);
    private static final String FIXTURE_SHA256 =
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

    @Test
    public void onlyTheTwoMainProcessesAreEligible() {
        assertTrue(ScopePolicy.isTargetMainProcess("com.android.systemui", "com.android.systemui"));
        assertTrue(ScopePolicy.isTargetMainProcess("com.google.oslo", "com.google.oslo"));
        assertFalse(ScopePolicy.isTargetMainProcess("com.google.oslo", "com.google.oslo:remote"));
        assertFalse(ScopePolicy.isTargetMainProcess("android", "system_server"));
        assertFalse(ScopePolicy.isTargetMainProcess("org.hecker.floral.motionsense", "org.hecker.floral.motionsense"));
    }

    @Test
    public void allowlistPreservesOrderDuplicatesAndOriginalArray() {
        String[] original = {"existing.plugin", "existing.plugin"};
        assertArrayEquals(new String[] {"existing.plugin", "existing.plugin", "com.google.oslo"},
                ScopePolicy.appendOslo(original));
        assertArrayEquals(new String[] {"existing.plugin", "existing.plugin"}, original);
        String[] present = {"existing.plugin", "com.google.oslo"};
        assertSame(present, ScopePolicy.appendOslo(present));
    }

    @Test
    public void permissionExceptionIsLimitedToOnePermissionAndOnePackage() {
        assertTrue(ScopePolicy.isPluginPermission(ScopePolicy.PLUGIN_PERMISSION, ScopePolicy.OSLO));
        assertFalse(ScopePolicy.isPluginPermission("android.permission.STATUS_BAR_SERVICE", ScopePolicy.OSLO));
        assertFalse(ScopePolicy.isPluginPermission(ScopePolicy.PLUGIN_PERMISSION, ScopePolicy.SETTINGS));
        assertFalse(ScopePolicy.isPluginPermission(null, ScopePolicy.OSLO));
    }

    @Test
    public void onlyAllAndCurrentBecomeTheActualUser() {
        assertEquals(10, ScopePolicy.localUserId(-1, 10));
        assertEquals(10, ScopePolicy.localUserId(-2, 10));
        assertEquals(-3, ScopePolicy.localUserId(-3, 10));
        assertEquals(0, ScopePolicy.localUserId(0, 10));
        assertEquals(11, ScopePolicy.localUserId(11, 10));
    }

    @Test
    public void settingsAndClockDoNotWidenTheRewriteBoundary() {
        for (String key : new String[] {"aware_enabled", "skip_gesture", "tap_gesture",
                "silence_gesture", "skip_gesture_direction"}) {
            assertTrue(ScopePolicy.isOsloSetting(key));
        }
        assertFalse(ScopePolicy.isOsloSetting("android_id"));
        assertFalse(ScopePolicy.isOsloSetting(null));
        assertTrue(ScopePolicy.isClockCommand("android.intent.action.SNOOZE_ALARM"));
        assertTrue(ScopePolicy.isClockCommand("android.intent.action.DISMISS_TIMER"));
        assertFalse(ScopePolicy.isClockCommand("android.intent.action.DISMISS_ALARM"));
        assertFalse(ScopePolicy.isClockCommand("android.intent.action.CALL"));
    }

    @Test
    public void settingsNeedsTheActualUnsharedUid() {
        assertTrue(ScopePolicy.isSettingsUid(10123, 10123, new String[] {ScopePolicy.SETTINGS}));
        assertFalse(ScopePolicy.isSettingsUid(10124, 10123, new String[] {ScopePolicy.SETTINGS}));
        assertFalse(ScopePolicy.isSettingsUid(10123, 10123, new String[] {"unrelated.package"}));
        assertFalse(ScopePolicy.isSettingsUid(10123, 10123,
                new String[] {ScopePolicy.SETTINGS, "other.shared.package"}));
        assertFalse(ScopePolicy.isSettingsUid(10123, 10123, null));
    }

    @Test
    public void onlyUnmodifiedSystemAppsAreAccepted() {
        assertTrue(ScopePolicy.isUnmodifiedSystemApp(true, false));
        assertFalse(ScopePolicy.isUnmodifiedSystemApp(true, true));
        assertFalse(ScopePolicy.isUnmodifiedSystemApp(false, false));
        assertFalse(ScopePolicy.isUnmodifiedSystemApp(false, true));
    }

    @Test
    public void onlyTheSingleCurrentProjectSignerIsAccepted() {
        assertTrue(ScopePolicy.matchesCertificate(new byte[][] {CERT_FIXTURE}, FIXTURE_SHA256));
        assertTrue(ScopePolicy.matchesCertificate(new byte[][] {CERT_FIXTURE}, FIXTURE_SHA256.toUpperCase()));
        assertFalse(ScopePolicy.matchesCertificate(new byte[][] {{1, 2, 3}}, FIXTURE_SHA256));
        assertFalse(ScopePolicy.matchesCertificate(new byte[][] {CERT_FIXTURE, CERT_FIXTURE}, FIXTURE_SHA256));
        assertFalse(ScopePolicy.matchesCertificate(null, FIXTURE_SHA256));
        assertFalse(ScopePolicy.matchesCertificate(new byte[][] {CERT_FIXTURE}, "unconfigured"));
    }
}
