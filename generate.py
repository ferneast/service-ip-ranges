#!/usr/bin/env python3
"""
Fetch IP ranges from upstream sources and generate combined.json.

Data sources:
- https://github.com/lord-alfred/ipranges (for services with upstream folders)
- BGPView API (for ASN-based lookups)
"""

import json
import urllib.request
import datetime
import sys

UPSTREAM_BASE = "https://raw.githubusercontent.com/lord-alfred/ipranges/main"
RIPE_STAT_API = "https://stat.ripe.net/data/announced-prefixes/data.json"

# Service definitions using upstream ipranges repo: (id, display_name, sf_symbol_icon, upstream_folder)
UPSTREAM_SERVICES = [
    ("google",    "Google",       "g.circle.fill",      "google"),
    ("meta",      "Meta",         "person.2.fill",      "facebook"),
    ("apple",     "Apple",        "apple.logo",          "apple-proxy"),
    ("github",    "GitHub",       "chevron.left.forwardslash.chevron.right", "github"),
    ("telegram",  "Telegram",     "paperplane.fill",    "telegram"),
    ("twitter",   "Twitter / X", "at",                  "twitter"),
    ("openai",    "OpenAI",       "cpu",                "openai"),
]

# Service definitions using ASN lookups: (id, display_name, sf_symbol_icon, [asn_numbers])
ASN_SERVICES = [
    ("netflix",     "Netflix",      "play.tv.fill",       [2906]),
    ("spotify",     "Spotify",      "music.note",         [35994, 202018, 394006]),
    ("tiktok",      "TikTok",       "music.note.tv",      [138699, 396986]),
    ("snapchat",    "Snapchat",     "camera.fill",        [13414]),
    ("discord",     "Discord",      "bubble.left.and.bubble.right.fill", [49544]),
    ("zoom",        "Zoom",         "video.fill",         [30103]),
    ("line",        "LINE",         "message.fill",       [38631]),
    ("steam",       "Steam",        "gamecontroller.fill", [32590]),
    ("pinterest",   "Pinterest",    "pin.fill",           [54113]),
    ("linkedin",    "LinkedIn",     "briefcase.fill",     [14413]),
    ("reddit",      "Reddit",       "text.bubble.fill",   [394536, 13238]),
    ("whatsapp",    "WhatsApp",     "phone.fill",         [63293]),
    ("disneyplus",  "Disney+",      "sparkles.tv.fill",   [11251, 7754]),
    ("hulu",        "Hulu",         "play.tv",            [23286]),
    ("signal",      "Signal",       "lock.fill",          [396507]),
    ("youtube",     "YouTube",      "play.rectangle.fill", [36040, 43515]),
]

# Service definitions with static IP ranges: (id, display_name, sf_symbol_icon, [ip_ranges])
STATIC_SERVICES = [
    ("claude", "Claude", "brain.fill", [
        "160.79.104.0/23",
        "160.79.104.0/21",
        "2607:6bc0::/48",
    ]),
]


def fetch_text(url: str) -> list[str]:
    """Fetch a text file and return non-empty lines."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "service-ip-ranges/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8")
            return [line.strip() for line in text.splitlines() if line.strip()]
    except Exception as e:
        print(f"  Warning: failed to fetch {url}: {e}", file=sys.stderr)
        return []


def fetch_upstream_service(folder: str) -> list[str]:
    """Fetch merged IPv4 and IPv6 ranges for an upstream service."""
    ipv4 = fetch_text(f"{UPSTREAM_BASE}/{folder}/ipv4_merged.txt")
    ipv6 = fetch_text(f"{UPSTREAM_BASE}/{folder}/ipv6_merged.txt")
    return ipv4 + ipv6


def fetch_asn_prefixes(asn: int) -> list[str]:
    """Fetch IP prefixes for a given ASN from RIPE STAT API."""
    url = f"{RIPE_STAT_API}?resource=AS{asn}&sourceapp=service-ip-ranges"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "service-ip-ranges/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            prefixes = []
            for entry in data.get("data", {}).get("prefixes", []):
                prefix = entry.get("prefix")
                if prefix:
                    prefixes.append(prefix)
            return prefixes
    except Exception as e:
        print(f"  Warning: failed to fetch ASN {asn}: {e}", file=sys.stderr)
        return []


def fetch_asn_service(asns: list[int]) -> list[str]:
    """Fetch and deduplicate IP ranges for a list of ASNs."""
    all_prefixes = []
    seen = set()
    for asn in asns:
        for prefix in fetch_asn_prefixes(asn):
            if prefix not in seen:
                seen.add(prefix)
                all_prefixes.append(prefix)
    return all_prefixes


def main():
    services = []

    # Fetch upstream services
    for service_id, name, icon, folder in UPSTREAM_SERVICES:
        print(f"Fetching {name} ({folder})...", file=sys.stderr)
        ip_ranges = fetch_upstream_service(folder)
        if not ip_ranges:
            print(f"  Skipping {name}: no IP ranges found", file=sys.stderr)
            continue
        services.append({
            "id": service_id,
            "name": name,
            "icon": icon,
            "ipRanges": ip_ranges,
        })
        print(f"  {name}: {len(ip_ranges)} ranges", file=sys.stderr)

    # Fetch ASN-based services
    for service_id, name, icon, asns in ASN_SERVICES:
        print(f"Fetching {name} (ASN {', '.join(str(a) for a in asns)})...", file=sys.stderr)
        ip_ranges = fetch_asn_service(asns)
        if not ip_ranges:
            print(f"  Skipping {name}: no IP ranges found", file=sys.stderr)
            continue
        services.append({
            "id": service_id,
            "name": name,
            "icon": icon,
            "ipRanges": ip_ranges,
        })
        print(f"  {name}: {len(ip_ranges)} ranges", file=sys.stderr)

    # Static services
    for service_id, name, icon, ip_ranges in STATIC_SERVICES:
        print(f"Adding {name} (static)...", file=sys.stderr)
        services.append({
            "id": service_id,
            "name": name,
            "icon": icon,
            "ipRanges": ip_ranges,
        })
        print(f"  {name}: {len(ip_ranges)} ranges", file=sys.stderr)

    output = {
        "version": 1,
        "lastUpdated": datetime.date.today().isoformat(),
        "services": services,
    }

    with open("combined.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    total = sum(len(s["ipRanges"]) for s in services)
    print(f"\nDone: {len(services)} services, {total} total IP ranges", file=sys.stderr)


if __name__ == "__main__":
    main()
