/* SPDX-License-Identifier: Apache-2.0 */
package io.github.mrmetatron.soli.adapter;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import de.robv.android.xposed.XposedBridge;

final class HookLog {
    private static final Set<String> SEEN = ConcurrentHashMap.newKeySet();

    private HookLog() {}

    static void once(String message) {
        if (SEEN.add(message)) {
            XposedBridge.log("SoliMotion: " + message);
        }
    }

    static void failure(String operation, Throwable error) {
        // No app data, media titles, incoming numbers or binder payloads in project logs.
        once(operation + ": " + error.getClass().getSimpleName());
    }
}
