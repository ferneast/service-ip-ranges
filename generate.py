#!/usr/bin/env python3
"""
Fetch IP ranges from upstream sources and generate combined.json.

SCOPE: inbound ranges only.
This data answers "which service is this IP?" for traffic a user's device
originates, so we only collect addresses a service SERVES on -- the ones
clients connect TO. A vendor's outbound/egress ranges (the source IPs it
connects out from: webhook delivery, crawlers, agent tool calls) never
appear in a user's own connection table, so they are deliberately excluded.

Data sources:
- https://github.com/lord-alfred/ipranges (for services with upstream folders)
- RIPE Stat API (for ASN-based lookups; announced prefixes are a service's
  own routed space, which is what it serves from)
- api.github.com/meta (ingress keys only)
"""

import ipaddress
import json
import urllib.request
import datetime
import sys

UPSTREAM_BASE = "https://raw.githubusercontent.com/lord-alfred/ipranges/main"
RIPE_STAT_API = "https://stat.ripe.net/data/announced-prefixes/data.json"
GITHUB_META_API = "https://api.github.com/meta"

# Service definitions using upstream ipranges repo: (id, display_name, sf_symbol_icon, upstream_folder)
UPSTREAM_SERVICES = [
    ("google",    "Google",       "g.circle.fill",      "google"),
    ("meta",      "Meta",         "person.2.fill",      "facebook"),
    ("telegram",  "Telegram",     "paperplane.fill",    "telegram"),
    ("twitter",   "Twitter / X", "at",                  "twitter"),
    # No "openai" entry on purpose. OpenAI publishes egress ranges only
    # (https://developers.openai.com/api/docs/guides/ip-addresses -> chatgpt-agents.json,
    # chatgpt-connectors.json; plus the gptbot/searchbot/chatgpt-user crawler lists),
    # and api.openai.com / chatgpt.com resolve into Cloudflare AS13335, not OpenAI
    # space. There is no OpenAI-owned inbound range to list, and listing Cloudflare's
    # would tag a large share of the web as OpenAI. The lord-alfred "openai" folder is
    # egress too (and has no ipv6_merged.txt).
]

# Service definitions using ASN lookups: (id, display_name, sf_symbol_icon, [asn_numbers])
ASN_SERVICES = [
    ("apple",       "Apple",        "apple.logo",         [714, 6185]),
    ("netflix",     "Netflix",      "play.tv.fill",       [2906]),
    ("spotify",     "Spotify",      "music.note",         [35994, 202018, 394006]),
    ("tiktok",      "TikTok",       "music.note.tv",      [138699, 396986]),
    ("snapchat",    "Snapchat",     "camera.fill",        [13414]),
    ("discord",     "Discord",      "bubble.left.and.bubble.right.fill", [49544]),
    ("zoom",        "Zoom",         "video.fill",         [30103]),
    ("line",        "LINE",         "message.fill",       [38631]),
    ("steam",       "Steam",        "gamecontroller.fill", [32590]),
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
    # https://platform.claude.com/docs/en/api/ip-addresses -- "Inbound IP addresses"
    # only. The doc's outbound ranges (160.79.104.0/21, 153.61.208.0/20) are
    # Anthropic's egress for MCP/web-search tool calls and are excluded on purpose;
    # note 160.79.104.0/21 is a supernet of the inbound /23, so including it would
    # silently widen this entry 8x.
    ("claude", "Claude", "brain.fill", [
        "160.79.104.0/23",
        "153.61.224.0/22",
        "2607:6bc0::/48",
    ]),
]


# Blocks a service owns entirely: {service_id: [cidr, ...]}
# These are added unconditionally and absorb every fetched sub-prefix.
# Apple owns all of 17.0.0.0/8, so ~1500 announced sub-prefixes collapse into one entry.
SERVICE_SUPERNETS = {
    "apple": ["17.0.0.0/8"],
}

def normalize_ranges(service_id: str, ip_ranges: list[str]) -> list[str]:
    """Add known supernets, then merge and deduplicate overlapping prefixes."""
    networks = []
    unparsed = []
    for prefix in SERVICE_SUPERNETS.get(service_id, []) + ip_ranges:
        try:
            networks.append(ipaddress.ip_network(prefix, strict=False))
        except ValueError:
            print(f"  Warning: skipping unparsable prefix {prefix!r}", file=sys.stderr)
            unparsed.append(prefix)

    merged = []
    for version in (4, 6):
        same_version = (n for n in networks if n.version == version)
        merged.extend(str(n) for n in ipaddress.collapse_addresses(same_version))
    return merged + unparsed


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


def fetch_github_ranges() -> list[str]:
    """Fetch IP ranges from GitHub's official meta API."""
    try:
        req = urllib.request.Request(GITHUB_META_API, headers={"User-Agent": "service-ip-ranges/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            seen = set()
            prefixes = []
            # Ingress keys only -- the addresses clients connect TO.
            # Excluded as egress (GitHub's own source IPs when it connects out):
            #   hooks                      webhook delivery
            #   importer / github_enterprise_importer
            #   actions / actions_macos    runner pools (8000+ Azure IPs)
            #   codespaces                 dev-container infra
            # ("dependabot" is no longer present in the API response at all.)
            for key in ("web", "api", "git", "packages", "pages",
                        "shared_ingress", "copilot"):
                for prefix in data.get(key, []):
                    if prefix not in seen:
                        seen.add(prefix)
                        prefixes.append(prefix)
            return prefixes
    except Exception as e:
        print(f"  Warning: failed to fetch GitHub meta API: {e}", file=sys.stderr)
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

    # Fetch GitHub from official API
    print("Fetching GitHub (api.github.com/meta)...", file=sys.stderr)
    github_ranges = fetch_github_ranges()
    if github_ranges:
        services.append({
            "id": "github",
            "name": "GitHub",
            "icon": "chevron.left.forwardslash.chevron.right",
            "ipRanges": github_ranges,
        })
        print(f"  GitHub: {len(github_ranges)} ranges", file=sys.stderr)
    else:
        print("  Skipping GitHub: no IP ranges found", file=sys.stderr)

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

    # Normalize: apply supernets, merge and deduplicate
    for service in services:
        before = len(service["ipRanges"])
        service["ipRanges"] = normalize_ranges(service["id"], service["ipRanges"])
        after = len(service["ipRanges"])
        if after != before:
            print(f"Normalizing {service['name']}: {before} -> {after} ranges", file=sys.stderr)

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
