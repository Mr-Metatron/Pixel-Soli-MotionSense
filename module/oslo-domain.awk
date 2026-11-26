# Copyright 2026 Pixel-Soli-MotionSense contributors. SPDX-License-Identifier: Apache-2.0
# Require the known vendor rule, with no extra input selectors that could exclude Oslo.
{
    sub(/#.*/, "")
    user = seinfo = name = domain = 0
    valid = 1
    for (i = 1; i <= NF; i++) {
        if ($i == "user=_app") user++
        else if ($i == "seinfo=platform") seinfo++
        else if ($i == "name=com.google.oslo") name++
        else if ($i == "domain=oslo_app") domain++
        else if ($i !~ /^(type|levelFrom|level)=/) valid = 0
    }
    if (valid && user == 1 && seinfo == 1 && name == 1 && domain == 1) found = 1
}
END { exit !found }
