"""
Search for Stark Financial Holdings LLC and similar entities in Wyoming.

Uses the OpenCorporates public API (no API key needed for basic searches)
and constructs direct Wyoming SOS search links for manual verification.

OpenCorporates API docs: https://api.opencorporates.com/documentation/API-Reference
"""

import requests
import json
import time
import sys
from urllib.parse import urlencode, quote_plus


OPENCORPORATES_API = "https://api.opencorporates.com/v0.4"

# Search terms — ordered from most specific to broadest
SEARCH_TERMS = [
    "Stark Financial Holdings",
    "Stark Financial Holdings LLC",
    "Stark Holdings",
    "Stark Financial",
    "Stark Wear",
    "Wear Stark",
]

HEADERS = {
    "User-Agent": "StarkEntitySearch/1.0 (research tool)",
    "Accept": "application/json",
}


def search_opencorporates(name: str, jurisdiction: str = "us_wy") -> list[dict]:
    """
    Query OpenCorporates for companies matching `name` in Wyoming (us_wy).

    Args:
        name:         Company name search string
        jurisdiction: OpenCorporates jurisdiction code (us_wy = Wyoming)

    Returns:
        List of normalised company dicts
    """
    results = []
    page = 1

    while True:
        params = {
            "q": name,
            "jurisdiction_code": jurisdiction,
            "per_page": 100,
            "page": page,
            "inactive": "true",   # include inactive / dissolved entities
        }

        url = f"{OPENCORPORATES_API}/companies/search"
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)

            if resp.status_code == 429:
                print(f"    Rate limited — waiting 10 s...")
                time.sleep(10)
                continue

            if resp.status_code != 200:
                print(f"    HTTP {resp.status_code} from OpenCorporates for '{name}'")
                break

            data = resp.json()
            companies = (
                data.get("results", {})
                    .get("companies", [])
            )

            if not companies:
                break

            for item in companies:
                co = item.get("company", {})
                results.append({
                    "Name":              co.get("name", ""),
                    "Company Number":    co.get("company_number", ""),
                    "Jurisdiction":      co.get("jurisdiction_code", ""),
                    "Status":            co.get("current_status", ""),
                    "Incorporation Date":co.get("incorporation_date", ""),
                    "Dissolution Date":  co.get("dissolution_date", ""),
                    "Company Type":      co.get("company_type", ""),
                    "Registered Address":co.get("registered_address_in_full", ""),
                    "OpenCorporates URL":co.get("opencorporates_url", ""),
                    "_search_term":      name,
                })

            total = data["results"].get("total_count", 0)
            fetched_so_far = page * 100
            if fetched_so_far >= total:
                break
            page += 1
            time.sleep(0.5)

        except requests.exceptions.RequestException as e:
            print(f"    Network error: {e}")
            break

    return results


def deduplicate(entities: list[dict]) -> list[dict]:
    """Remove duplicates keyed on (Name, Company Number)."""
    seen: set[tuple] = set()
    unique = []
    for e in entities:
        key = (e.get("Name", "").upper(), e.get("Company Number", ""))
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def score_relevance(entity: dict) -> int:
    """
    Score how closely an entity matches 'Stark Financial Holdings LLC'.
    Higher = more relevant.
    """
    name = entity.get("Name", "").upper()
    score = 0

    if "STARK" in name:
        score += 10
    if "FINANCIAL" in name:
        score += 5
    if "HOLDINGS" in name:
        score += 5
    if "LLC" in name:
        score += 2
    if "WEAR" in name:
        score += 3

    return score


def display_results(all_results: list[dict]) -> None:
    """Print results sorted by relevance."""
    if not all_results:
        print("\nNo matching entities found.")
        return

    sorted_results = sorted(all_results, key=score_relevance, reverse=True)

    print(f"\n{'='*70}")
    print(f"  FOUND {len(sorted_results)} STARK-RELATED ENTITIES IN WYOMING")
    print(f"{'='*70}")

    for i, entity in enumerate(sorted_results, 1):
        print(f"\n[{i}]  {entity.get('Name', 'N/A')}")
        print(f"      Company #:    {entity.get('Company Number', 'N/A')}")
        print(f"      Status:       {entity.get('Status', 'N/A')}")
        print(f"      Type:         {entity.get('Company Type', 'N/A')}")
        print(f"      Incorporated: {entity.get('Incorporation Date', 'N/A')}")
        diss = entity.get("Dissolution Date")
        if diss:
            print(f"      Dissolved:    {diss}")
        addr = entity.get("Registered Address")
        if addr:
            print(f"      Address:      {addr}")
        oc_url = entity.get("OpenCorporates URL")
        if oc_url:
            print(f"      Source:       {oc_url}")
        print(f"      {'-'*55}")


def print_manual_links() -> None:
    """Print links for manual verification on Wyoming SOS."""
    base = "https://wyobiz.wyo.gov/Business/FilingSearch.aspx"
    print("\nManual verification links (Wyoming Secretary of State):")
    print("-" * 55)
    for term in SEARCH_TERMS:
        encoded = quote_plus(term)
        # Wyoming SOS uses a POST form; these GET params may pre-fill the form
        print(f"  '{term}'\n  => {base}?nameCriteria={encoded}&searchType=CN\n")


def main():
    print("Stark Entity Search — Wyoming Secretary of State data via OpenCorporates")
    print("=" * 70)

    all_results: list[dict] = []

    for term in SEARCH_TERMS:
        print(f"\nSearching: '{term}'")
        results = search_opencorporates(term)
        if results:
            print(f"  -> {len(results)} result(s) found")
        else:
            print(f"  -> No results")
        all_results.extend(results)
        time.sleep(1)

    all_results = deduplicate(all_results)
    display_results(all_results)

    # Save output
    output_file = "stark_entities_wyoming.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull results saved to: {output_file}")

    print_manual_links()

    return all_results


if __name__ == "__main__":
    main()
