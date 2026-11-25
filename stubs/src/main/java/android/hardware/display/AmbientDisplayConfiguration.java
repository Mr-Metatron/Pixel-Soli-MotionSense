// SPDX-License-Identifier: Apache-2.0
package android.hardware.display;

import android.content.Context;

/** Signatures pinned to the target LOS framework, never packaged in an APK. */
public class AmbientDisplayConfiguration {
    public AmbientDisplayConfiguration(Context context) {
        throw new UnsupportedOperationException("Compile-only framework stub");
    }

    public boolean alwaysOnAvailableForUser(int userId) {
        throw new UnsupportedOperationException("Compile-only framework stub");
    }

    public boolean alwaysOnEnabled(int userId) {
        throw new UnsupportedOperationException("Compile-only framework stub");
    }

    public boolean wakeDisplayGestureEnabled(int userId) {
        throw new UnsupportedOperationException("Compile-only framework stub");
    }
}
