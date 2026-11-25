/* Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0 */
package io.github.mrmetatron.soli.identity;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.StringReader;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.cert.CertificateFactory;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;

/** One-shot pre-mount XML merge, runnable with the system dalvikvm. */
public final class Main {
    private static final String PACKAGE = "com.google.oslo";
    private static final int MAX_INPUT_BYTES = 4 * 1024 * 1024;

    private Main() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            throw new IllegalArgumentException("Usage: Main ROM_XML OUTPUT_XML CERT_DER_HEX");
        }
        File source = new File(args[0]);
        File target = new File(args[1]);
        if (source.getCanonicalPath().equals(target.getCanonicalPath())) {
            throw new IllegalArgumentException("Source must remain unchanged");
        }
        String input = readLimited(source);
        String cert = validateCertificate(readLimited(new File(args[2])).trim());
        String merged = merge(input, cert);
        // Reparse the serialized document before it can become a mount target.
        parse(merged);
        File temporary = new File(target.getPath() + ".tmp");
        try {
            try (FileOutputStream out = new FileOutputStream(temporary)) {
                out.write(merged.getBytes(StandardCharsets.UTF_8));
                out.getFD().sync();
            }
            if (!temporary.renameTo(target)) {
                throw new IllegalStateException("Could not atomically install merged XML");
            }
        } finally {
            temporary.delete();
        }
        System.out.println("Merged project signer for com.google.oslo; existing ROM entries preserved.");
    }

    private static String readLimited(File file) throws Exception {
        if (file.length() == 0 || file.length() > MAX_INPUT_BYTES) {
            throw new IllegalArgumentException("Empty or oversized input: " + file.getName());
        }
        return new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
    }

    static String validateCertificate(String hex) throws Exception {
        if (hex.length() < 256 || hex.length() > 32768 || (hex.length() & 1) != 0
                || !hex.matches("[0-9a-fA-F]+")) {
            throw new IllegalArgumentException("Expected full X.509 certificate DER hex");
        }
        byte[] bytes = new byte[hex.length() / 2];
        for (int i = 0; i < bytes.length; i++) {
            bytes[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        ByteArrayInputStream in = new ByteArrayInputStream(bytes);
        CertificateFactory.getInstance("X.509").generateCertificate(in);
        if (in.available() != 0) {
            throw new IllegalArgumentException("Trailing data after certificate");
        }
        return hex.toLowerCase(Locale.ROOT);
    }

    private static Document parse(String text) throws Exception {
        // mac_permissions has no DTD. Reject it before either Android or JDK parser runs.
        if (text.contains("<!DOCTYPE") || text.indexOf('\0') >= 0) {
            throw new IllegalArgumentException("DTD and non-UTF-8 XML are not supported");
        }
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(false);
        factory.setExpandEntityReferences(false);
        DocumentBuilder builder = factory.newDocumentBuilder();
        builder.setEntityResolver((publicId, systemId) -> {
            throw new SAXException("External XML entities are not allowed");
        });
        Document document = builder.parse(new InputSource(new StringReader(text)));
        if (!"policy".equals(document.getDocumentElement().getTagName())) {
            throw new IllegalArgumentException("Expected mac_permissions policy root");
        }
        return document;
    }

    static String merge(String input, String cert) throws Exception {
        Document document = parse(input);
        Element policy = document.getDocumentElement();
        Element matching = null;
        for (Element signer : children(policy, "signer")) {
            if (!cert.equalsIgnoreCase(signer.getAttribute("signature"))) {
                continue;
            }
            if (matching != null) {
                throw new IllegalArgumentException("Duplicate project signer in ROM XML");
            }
            matching = signer;
        }
        if (matching == null) {
            matching = document.createElement("signer");
            matching.setAttribute("signature", cert);
            policy.appendChild(matching);
        }
        // A project signer must never assign platform to all packages sharing its key.
        if (!children(matching, "seinfo").isEmpty()) {
            throw new IllegalArgumentException("Project signer already has an unscoped seinfo");
        }
        Element oslo = null;
        for (Element item : children(matching, "package")) {
            if (!PACKAGE.equals(item.getAttribute("name"))) {
                continue;
            }
            if (oslo != null) {
                throw new IllegalArgumentException("Duplicate Oslo entry in project signer");
            }
            oslo = item;
        }
        if (oslo == null) {
            oslo = document.createElement("package");
            oslo.setAttribute("name", PACKAGE);
            Element seinfo = document.createElement("seinfo");
            seinfo.setAttribute("value", "platform");
            oslo.appendChild(seinfo);
            matching.appendChild(oslo);
        } else {
            List<Element> seinfo = children(oslo, "seinfo");
            if (seinfo.size() != 1 || !"platform".equals(seinfo.get(0).getAttribute("value"))) {
                throw new IllegalArgumentException("Conflicting existing Oslo identity");
            }
        }
        Transformer transformer = TransformerFactory.newInstance().newTransformer();
        transformer.setOutputProperty(OutputKeys.ENCODING, "utf-8");
        transformer.setOutputProperty(OutputKeys.INDENT, "no");
        StringWriter result = new StringWriter();
        transformer.transform(new DOMSource(document), new StreamResult(result));
        return result.toString();
    }

    private static List<Element> children(Element parent, String tag) {
        List<Element> result = new ArrayList<>();
        for (Node node = parent.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (node instanceof Element && tag.equals(((Element) node).getTagName())) {
                result.add((Element) node);
            }
        }
        return result;
    }
}

