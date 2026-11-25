/* Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0 */
package io.github.mrmetatron.soli.identity;

/** Host regression tests for the boot-critical merge; no Android service dependencies. */
public final class MainTest {
    private static int checks;
    private static final String CERT = "abcd";

    public static void main(String[] args) throws Exception {
        String original = "<?xml version=\"1.0\"?><policy><!-- ROM -->"
                + "<signer signature=\"face\"><seinfo value=\"platform\"/></signer>"
                + "<signer signature=\"cafe\"><package name=\"example.other\">"
                + "<seinfo value=\"media\"/></package></signer></policy>";
        String merged = Main.merge(original, CERT);
        check(merged.contains("<!-- ROM -->"), "ROM comments retained");
        check(merged.contains("signature=\"face\""), "ROM signer retained");
        check(merged.contains("name=\"example.other\""), "Other package retained");
        check(merged.contains("<signer signature=\"abcd\"><package name=\"com.google.oslo\">"),
                "Project mapping is package-scoped");
        check(Main.merge(merged, CERT).equals(merged), "Merge is idempotent");
        String sibling = Main.merge("<policy><signer signature=\"ABCD\">"
                + "<package name=\"example.sibling\"><seinfo value=\"other\"/></package>"
                + "</signer></policy>", CERT);
        check(sibling.contains("example.sibling"), "Existing project-key sibling retained");
        rejects("<policy><broken></policy>");
        rejects("<permissions/>");
        rejects("<!DOCTYPE policy [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><policy>&x;</policy>");
        rejects("<policy><signer signature=\"abcd\"><seinfo value=\"platform\"/></signer></policy>");
        rejects("<policy><signer signature=\"abcd\"/><signer signature=\"ABCD\"/></policy>");
        rejects("<policy><signer signature=\"abcd\"><package name=\"com.google.oslo\">"
                + "<seinfo value=\"wrong\"/></package></signer></policy>");
        try {
            Main.validateCertificate("f".repeat(64));
            throw new AssertionError("SHA256 digest must not be accepted as DER certificate");
        } catch (IllegalArgumentException expected) {
            checks++;
        }
        System.out.println("Identity merge: " + checks + " checks passed");
    }

    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
        checks++;
    }

    private static void rejects(String input) throws Exception {
        try {
            Main.merge(input, CERT);
        } catch (Exception expected) {
            checks++;
            return;
        }
        throw new AssertionError("Malformed or conflicting XML accepted");
    }
}
