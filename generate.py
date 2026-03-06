#!/usr/bin/env python3
"""
Fetch IP ranges from upstream sources and generate combined.json.

Data source: https://github.com/lord-alfred/ipranges
"""

import json
import urllib.request
import datetime
import sys

UPSTREAM_BASE = "https://raw.githubusercontent.com/lord-alfred/ipranges/main"

# Service definitions: (id, display_name, sf_symbol_icon, upstream_folder)
SERVICES = [
    ("google",       "Google",        "g.circle.fill",           "google"),
    ("meta",         "Meta",          "person.2.fill",           "facebook"),
    ("amazon",       "Amazon AWS",    "server.rack",             "amazon"),
    ("microsoft",    "Microsoft",     "desktopcomputer",         "microsoft"),
    ("apple",        "Apple",         "apple.logo",              "apple-proxy"),
    ("cloudflare",   "Cloudflare",    "shield.fill",             "cloudflare"),
    ("github",       "GitHub",        "chevron.left.forwardslash.chevron.right", "github"),
    ("oracle",       "Oracle Cloud",  "cloud.fill",              "oracle"),
    ("digitalocean", "DigitalOcean",  "drop.fill",               "digitalocean"),
    ("telegram",     "Telegram",      "paperplane.fill",         "telegram"),
    ("twitter",      "Twitter / X",   "at",                      "twitter"),
    ("openai",       "OpenAI",        "cpu",                     "openai"),
    ("linode",       "Linode",        "network",                 "linode"),
    ("vultr",        "Vultr",         "externaldrive.connected.to.line.below.fill", "vultr"),
    ("protonvpn",    "ProtonVPN",     "lock.shield.fill",        "protonvpn"),
    ("perplexity",   "Perplexity",    "magnifyingglass",         "perplexity"),
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


def fetch_service(folder: str) -> list[str]:
    """Fetch merged IPv4 and IPv6 ranges for a service."""
    ipv4 = fetch_text(f"{UPSTREAM_BASE}/{folder}/ipv4_merged.txt")
    ipv6 = fetch_text(f"{UPSTREAM_BASE}/{folder}/ipv6_merged.txt")
    return ipv4 + ipv6


def main():
    services = []
    for service_id, name, icon, folder in SERVICES:
        print(f"Fetching {name} ({folder})...", file=sys.stderr)
        ip_ranges = fetch_service(folder)
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
