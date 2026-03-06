# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project aggregates IP ranges for major internet services into a single `combined.json` file. It serves as a data source for applications that need to identify which service owns a given IP address (e.g., network monitoring tools, iOS apps).

## How It Works

`generate.py` fetches IP ranges from two source types and writes `combined.json`:

1. **Upstream services** (`UPSTREAM_SERVICES`) — pulled from the [lord-alfred/ipranges](https://github.com/lord-alfred/ipranges) GitHub repo (merged IPv4/IPv6 text files)
2. **ASN-based services** (`ASN_SERVICES`) — looked up via the RIPE Stat API using AS numbers

A GitHub Actions workflow (`.github/workflows/update.yml`) runs `python3 generate.py` daily at 06:00 UTC and auto-commits changes to `combined.json`.

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
- Each entry needs: `(id, display_name, sf_symbol_icon, source)` where source is a folder name or list of ASN integers
- The `icon` field uses Apple SF Symbols names (this data is consumed by an iOS app)
