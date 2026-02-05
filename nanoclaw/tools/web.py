"""Web search and fetch tools."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from urllib.parse import urlparse

import aiohttp

from nanoclaw.core.llm import ConnectionPool
from nanoclaw.core.logger import get_logger
from nanoclaw.tools.registry import tool

logger = get_logger(__name__)


def _is_private_ip(hostname: str) -> bool:
    """Check if a literal IP is private/loopback/link-local (no DNS)."""
    try:
        addr = ipaddress.ip_address(hostname)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


async def _is_private_host(hostname: str) -> bool:
    """Check if a hostname resolves to a private/loopback/link-local IP."""
    # Fast path: literal IP — no DNS needed
    if _is_private_ip(hostname):
        return True

    # DNS resolution in a thread to avoid blocking the event loop
    def _resolve() -> bool:
        try:
            for info in socket.getaddrinfo(hostname, None):
                addr = ipaddress.ip_address(info[4][0])
                if addr.is_private or addr.is_loopback or addr.is_link_local:
                    return True
        except (socket.gaierror, ValueError):
            pass
        return False

    return await asyncio.to_thread(_resolve)


# Simple rate limiter for Brave API (1 request per second)
_last_search_time: float = 0.0
_search_lock = asyncio.Lock()


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
    global _last_search_time

    try:
        from nanoclaw.core.config import get_config

        config = get_config()
        api_key = config.tools.web_search.api_key
    except Exception:
        api_key = ""

    if not api_key:
        return "Web search not configured. Add Brave API key to config."

    # Rate limiting: max 1 request per second to avoid 429
    async with _search_lock:
        now = time.time()
        elapsed = now - _last_search_time
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        _last_search_time = time.time()

    session = await ConnectionPool.get_session()
    max_retries = 3
    last_error = ""

    for attempt in range(max_retries):
        try:
            async with session.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5},
                headers={"X-Subscription-Token": api_key},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 429:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # 1s, 2s backoff
                        continue
                    return "Search rate limited. Try a different query or wait."
                if resp.status != 200:
                    return f"Search failed: HTTP {resp.status}"
                data = await resp.json()
                break  # success
        except aiohttp.ClientError as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            return f"Search failed: {last_error}"
        except Exception as e:
            return f"Search error: {e}"
    else:
        return f"Search failed after {max_retries} retries: {last_error}"

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
    # SSRF protection: block private/loopback/link-local addresses
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if not hostname:
            return "Invalid URL: no hostname"
        if await _is_private_host(hostname):
            return "BLOCKED: cannot fetch private/internal addresses"
    except Exception:
        return "Invalid URL"

    try:
        session = await ConnectionPool.get_session()
        max_redirects = 5
        current_url = url
        for _ in range(max_redirects):
            async with session.get(
                current_url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; nanoClaw/1.0; "
                        "+https://github.com/nanoclaw)"
                    ),
                    "Accept-Encoding": "gzip, deflate",
                },
                allow_redirects=False,
            ) as resp:
                if resp.status in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location", "")
                    if not location:
                        return "Redirect with no Location header"
                    # Validate redirect target against SSRF
                    try:
                        redir_parsed = urlparse(location)
                        redir_host = redir_parsed.hostname or ""
                        if redir_host and await _is_private_host(redir_host):
                            return "BLOCKED: redirect points to private/internal address"
                    except Exception:
                        return "BLOCKED: invalid redirect URL"
                    current_url = location
                    continue

                if resp.status != 200:
                    return f"Failed to fetch: HTTP {resp.status}"

                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type and "text/plain" not in content_type:
                    return f"Not a text page. Content-Type: {content_type}"

                html = await resp.text()
                break
        else:
            return "Too many redirects"
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
