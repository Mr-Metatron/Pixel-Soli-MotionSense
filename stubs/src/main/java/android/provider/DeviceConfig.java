// SPDX-License-Identifier: Apache-2.0
package android.provider;

/** Compile-only declaration. Reads use the ROM's normal permission checks. */
public final class DeviceConfig {
    private DeviceConfig() {}

    public static boolean getBoolean(String namespace, String name, boolean defaultValue) {
        throw new UnsupportedOperationException("Compile-only framework stub");
    }
}
