"""Web search and fetch tools."""

from __future__ import annotations

import aiohttp

from nanoclaw.core.llm import ConnectionPool
from nanoclaw.core.logger import get_logger
from nanoclaw.tools.registry import tool

logger = get_logger(__name__)


@tool(
    name="web_search",
    description=(
        "Search the internet for current information. "
        "Returns top 5 results with titles, URLs, and snippets."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "Search query, keep it concise (1-6 words work best)",
        }
    },
)
async def web_search(query: str) -> str:
    """Search using Brave Search API."""
    try:
        from nanoclaw.core.config import get_config

        config = get_config()
        api_key = config.tools.web_search.api_key
    except Exception:
        api_key = ""

    if not api_key:
        return "Web search not configured. Add Brave API key to config."

    try:
        session = await ConnectionPool.get_session()
        async with session.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 5},
            headers={"X-Subscription-Token": api_key},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return f"Search failed: HTTP {resp.status}"
            data = await resp.json()
    except aiohttp.ClientError as e:
        return f"Search failed: {e}"
    except Exception as e:
        return f"Search error: {e}"

    results = []
    for r in data.get("web", {}).get("results", [])[:5]:
        results.append(
            f"**{r['title']}**\n{r['url']}\n{r.get('description', '')}"
        )

    return "\n\n".join(results) if results else "No results found."


@tool(
    name="web_fetch",
    description=(
        "Fetch and read the content of a web page. "
        "Returns clean text extracted from HTML. "
        "Good for reading articles, documentation, blog posts."
    ),
    parameters={
        "url": {
            "type": "string",
            "description": "Full URL to fetch (https://...)",
        }
    },
)
async def web_fetch(url: str) -> str:
    """
    Fetch URL and convert HTML to readable text.

    Works for 90% of sites (articles, blogs, docs).
    Does NOT work for SPAs requiring JavaScript.
    """
    try:
        session = await ConnectionPool.get_session()
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=15),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; nanoClaw/1.0; "
                    "+https://github.com/nanoclaw)"
                )
            },
            allow_redirects=True,
        ) as resp:
            if resp.status != 200:
                return f"Failed to fetch: HTTP {resp.status}"

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return f"Not a text page. Content-Type: {content_type}"

            html = await resp.text()
    except aiohttp.ClientError as e:
        return f"Network error fetching {url}: {e}"
    except Exception as e:
        return f"Error fetching {url}: {e}"

    # Convert HTML to readable text
    try:
        import html2text

        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = True
        converter.body_width = 0  # No wrapping
        text = converter.handle(html)
    except ImportError:
        # Fallback: basic HTML stripping
        import re

        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()

    # Truncate to keep context lean
    if len(text) > 4000:
        text = text[:4000] + "\n\n...[content truncated at 4000 chars]"

    return text
