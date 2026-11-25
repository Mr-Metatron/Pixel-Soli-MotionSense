// SPDX-License-Identifier: Apache-2.0
package android.os;

/** Compile-only declaration. The device framework provides the implementation. */
public final class SystemProperties {
    private SystemProperties() {}

    public static boolean getBoolean(String key, boolean defaultValue) {
        throw new UnsupportedOperationException("Compile-only framework stub");
    }
}
