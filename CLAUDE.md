# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project aggregates IP ranges for major internet services into a single `combined.json` file. It serves as a data source for applications that need to identify which service owns a given IP address (e.g., network monitoring tools, iOS apps).

## Scope: inbound ranges only

The consumer resolves IPs seen in a user's own connection table, so only
**inbound** ranges belong here — the addresses a service *serves on*, which
clients connect **to**.

A vendor's **outbound/egress** ranges (the source IPs it connects out *from*:
webhook delivery, crawlers, agent tool calls) never appear in a user's
connection table, so they are excluded even when the vendor publishes them
prominently. Two consequences worth knowing before "fixing" an apparent gap:

- **Claude** publishes both. Only the `Inbound IP addresses` section is used.
  Its outbound `160.79.104.0/21` is a *supernet* of the inbound `160.79.104.0/23`,
  so pasting in the whole doc silently widens the entry 8x.
- **OpenAI is absent, deliberately.** It publishes egress ranges only, and
  `api.openai.com` / `chatgpt.com` resolve into Cloudflare (AS13335) rather than
  OpenAI-owned space. There is no OpenAI inbound range to list, and listing
  Cloudflare's would tag a large share of the web as OpenAI.

ASN-based services are unaffected: a service's announced prefixes are its own
routed space, which is what it serves from.

## How It Works

`generate.py` fetches IP ranges from three source types and writes `combined.json`:

1. **Upstream services** (`UPSTREAM_SERVICES`) — pulled from the [lord-alfred/ipranges](https://github.com/lord-alfred/ipranges) GitHub repo (merged IPv4/IPv6 text files)
2. **ASN-based services** (`ASN_SERVICES`) — looked up via the RIPE Stat API using AS numbers
3. **Static services** (`STATIC_SERVICES`) — hardcoded IP ranges defined directly in `generate.py`

GitHub is a special case fetched from `api.github.com/meta` by `fetch_github_ranges()`,
which reads the ingress keys only (`web`, `api`, `git`, `packages`, `pages`,
`shared_ingress`, `copilot`) and skips the egress ones (`hooks`, `importer`,
`github_enterprise_importer`, `actions`, `actions_macos`, `codespaces`).

Before writing the output, every service's ranges pass through `normalize_ranges()`:

- Blocks listed in `SERVICE_SUPERNETS` are added unconditionally (e.g. Apple owns all of `17.0.0.0/8`)
- Overlapping and adjacent prefixes are merged and deduplicated via `ipaddress.collapse_addresses`

A GitHub Actions workflow (`.github/workflows/update.yml`) runs `python3 generate.py` daily at 06:00 UTC and auto-commits changes to `combined.json`. It can also be triggered manually via `workflow_dispatch`.

## Commands

```bash
# Generate/update combined.json (requires network access)
python3 generate.py
```

No dependencies beyond Python 3.12+ standard library. No virtual environment needed.

## Output Format

`combined.json` structure:
```json
{
  "version": 1,
  "lastUpdated": "YYYY-MM-DD",
  "services": [
    {
      "id": "service_id",
      "name": "Display Name",
      "icon": "sf_symbol_name",
      "ipRanges": ["1.2.3.0/24", "2001:db8::/32"]
    }
  ]
}
```

## Adding a New Service

- For services covered by lord-alfred/ipranges: add a tuple to `UPSTREAM_SERVICES` in `generate.py`
- For services identifiable by ASN: add a tuple to `ASN_SERVICES` in `generate.py`
- For services with fixed/known IP ranges: add a tuple to `STATIC_SERVICES` in `generate.py`
- Each entry needs: `(id, display_name, sf_symbol_icon, source)` where source is a folder name, list of ASN integers, or list of CIDR strings
- Check the direction first: if the vendor's published list is egress-only, the service does not belong here (see **Scope** above)
- The `icon` field uses Apple SF Symbols names (this data is consumed by an iOS app)
