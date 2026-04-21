import requests
import time
from typing import List, Dict
from src.config import GOOGLE_CLOUD_API_KEY


SAFE_BROWSING_URL = (
    "https://safebrowsing.googleapis.com/v4/threatMatches:find"
)

# In-memory cache
_safe_cache = {}


def _query_google(urls: List[str]) -> Dict[str, bool]:
    if not urls:
        return {}

    payload = {
        "client": {
            "clientId": "relationship-pipeline",
            "clientVersion": "1.0"
        },
        "threatInfo": {
            "threatTypes": [
                "MALWARE",
                "SOCIAL_ENGINEERING",
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION"
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [
                {"url": u} for u in urls
            ]
        }
    }

    response = requests.post(
        f"{SAFE_BROWSING_URL}?key={GOOGLE_CLOUD_API_KEY}",
        json=payload,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    unsafe_urls = set()

    for match in data.get("matches", []):
        threat = match.get("threat", {})
        url = threat.get("url")
        if url:
            unsafe_urls.add(url)

    return {
        u: u not in unsafe_urls
        for u in urls
    }


def evaluate_link_safety(urls: List[str]) -> Dict:
    """
    Returns:

    {
        "links": [...],
        "safety_score": float
    }
    """

    urls = list(dict.fromkeys(urls))

    uncached = [
        u for u in urls
        if u not in _safe_cache
    ]

    if uncached:
        results = _query_google(uncached)

        for url, safe in results.items():
            _safe_cache[url] = safe

    evaluated_links = []

    safe_count = 0

    for url in urls:
        is_safe = _safe_cache.get(url, True)

        if is_safe:
            safe_count += 1

        evaluated_links.append({
            "url": url,
            "is_safe": is_safe,
        })

    total = len(urls)

    safety_score = (
        safe_count / total
        if total > 0
        else 1.0
    )

    return {
        "links": evaluated_links,
        "safety_score": round(safety_score, 3)
    }

# test
# print(evaluate_link_safety(["https://axsometherapeuticsinc.gcs-web.com/node/10236/pdf" , "https://investor.jazzpharma.com/node/19196/pdf" , "https://www.jazzpharma.com/news-releases/news-release-details/jazz-pharmaceuticals-completes-us-divestiture-sunosir-solriamfetol" , "https://axsome.com/investors/press-releases/press-release-details/2022/Axsome-Therapeutics-to-Acquire-Sunosi-from-Jazz-Pharmaceuticals-Expanding-Axsomes-Leadership-in-Neuroscience/default.aspx" , "https://investor.jazzpharma.com/news-releases/news-release-details/jazz-pharmaceuticals-announces-agreement-divest-sunosir/" , "https://investor.jazzpharma.com/news-releases/news-release-details/jazz-pharmaceuticals-completes-us-divestiture-sunosir/"]))