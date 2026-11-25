// SPDX-License-Identifier: Apache-2.0
package com.android.settingslib.widget.theme.flags;

/** Standalone equivalent of the SettingsLib build-time expressive-theme flag. */
public final class Flags {
    private Flags() {}

    public static boolean isExpressiveDesignEnabled() {
        return true;
    }
}
