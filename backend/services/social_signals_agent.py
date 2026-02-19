"""
Social Signals Agent — Aggregates social media presence and engagement.

- LinkedIn company followers + growth rate (via Enrichlyer)
- Twitter/X followers + recent tweet activity (via ScraperAPI)
- YouTube channel stats if applicable
- GitHub stars, forks, contributor count (enhances existing GitHubClient)
"""
import os
import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

import db as database
from integrations.clients import GitHubClient, ScraperClient, EnrichlyrClient

logger = logging.getLogger(__name__)


class SocialSignalsAgent:
    """Aggregates social media signals from multiple platforms."""

    def __init__(self):
        self.scraper = ScraperClient()
        self.github = GitHubClient()
        self.enrichlyr = EnrichlyrClient()

    async def gather_signals(
        self,
        company_id: str,
        company_name: str,
        company_domain: Optional[str] = None,
        website_data: Optional[dict] = None,
    ) -> dict:
        """Gather social signals from all available platforms."""
        tasks = {
            "github": self._github_signals(company_name),
            "twitter": self._twitter_signals(company_name, company_domain),
        }

        if company_domain:
            tasks["linkedin"] = self._linkedin_company_signals(company_domain)

        # Detect YouTube from website or common patterns
        youtube_url = self._find_youtube(website_data, company_name)
        if youtube_url:
            tasks["youtube"] = self._youtube_signals(youtube_url)

        names = list(tasks.keys())
        coros = list(tasks.values())
        gathered = await asyncio.gather(*coros, return_exceptions=True)

        results = {}
        for name, result in zip(names, gathered):
            if isinstance(result, Exception):
                logger.warning(f"[SocialSignals] {name} failed: {result}")
                results[name] = {"error": str(result)}
            else:
                results[name] = result

        # Compute composite social score
        results["composite_score"] = self._compute_score(results)
        results["gathered_at"] = datetime.now(timezone.utc).isoformat()

        # Store in DB
        try:
            enrichment_tbl = database.enrichment_collection()
            enrichment_tbl.insert({
                "company_id": company_id,
                "source_type": "social_signals",
                "source_url": f"multi-platform",
                "data": results,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_valid": True,
            })
        except Exception as e:
            logger.error(f"[SocialSignals] DB store failed: {e}")

        return results

    # ─── GitHub Signals ───────────────────────────────────────────────

    async def _github_signals(self, company_name: str) -> dict:
        """Enhanced GitHub signals: stars, forks, contributors, commit frequency."""
        org = await self.github.find_organization(company_name)
        if not org.get("found"):
            return {"found": False, "platform": "github"}

        repos = await self.github.analyze_repositories(org.get("login", ""))

        return {
            "found": True,
            "platform": "github",
            "org_name": org.get("login"),
            "org_url": org.get("html_url"),
            "public_repos": org.get("public_repos", 0),
            "followers": org.get("followers", 0),
            "total_stars": repos.get("total_stars", 0),
            "total_forks": repos.get("total_forks", 0),
            "tech_stack": repos.get("tech_stack", []),
            "engineering_velocity": repos.get("engineering_velocity", "unknown"),
            "top_repos": repos.get("recent_repos", [])[:3],
            "signal_strength": self._rate_github(repos),
        }

    def _rate_github(self, repos: dict) -> str:
        stars = repos.get("total_stars", 0)
        if stars >= 1000:
            return "strong"
        if stars >= 100:
            return "moderate"
        if stars > 0:
            return "weak"
        return "none"

    # ─── Twitter/X Signals ────────────────────────────────────────────

    async def _twitter_signals(self, company_name: str, domain: Optional[str]) -> dict:
        """Scrape Twitter/X profile for followers + recent activity."""
        # Try common Twitter handle patterns
        handles_to_try = [
            company_name.lower().replace(" ", ""),
            company_name.lower().replace(" ", "_"),
        ]
        if domain:
            handles_to_try.insert(0, domain.split(".")[0])

        for handle in handles_to_try[:3]:
            try:
                scraper_key = os.getenv("SCRAPER_API_KEY")
                if not scraper_key:
                    return {"found": False, "platform": "twitter", "reason": "No ScraperAPI key"}

                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.get(
                        "http://api.scraperapi.com",
                        params={
                            "api_key": scraper_key,
                            "url": f"https://nitter.net/{handle}",
                            "render": "false",
                        },
                    )

                if resp.status_code == 200 and "not found" not in resp.text.lower():
                    return self._parse_twitter_page(resp.text, handle)

            except Exception:
                continue

        return {"found": False, "platform": "twitter"}

    def _parse_twitter_page(self, html: str, handle: str) -> dict:
        """Extract follower count and recent tweet info from Nitter HTML."""
        followers = 0
        tweets_count = 0

        # Extract follower count
        follower_match = re.search(r'(\d[\d,]*)\s*Followers', html)
        if follower_match:
            followers = int(follower_match.group(1).replace(",", ""))

        tweets_match = re.search(r'(\d[\d,]*)\s*Tweets', html)
        if tweets_match:
            tweets_count = int(tweets_match.group(1).replace(",", ""))

        return {
            "found": True,
            "platform": "twitter",
            "handle": f"@{handle}",
            "followers": followers,
            "tweets_count": tweets_count,
            "signal_strength": "strong" if followers >= 10000 else "moderate" if followers >= 1000 else "weak",
        }

    # ─── LinkedIn Company Signals ─────────────────────────────────────

    async def _linkedin_company_signals(self, company_domain: str) -> dict:
        """Fetch LinkedIn company signals via Enrichlyer."""
        if not self.enrichlyr.api_key:
            return {"found": False, "platform": "linkedin", "reason": "No Enrichlyer key"}

        try:
            data = await self.enrichlyr.get_company_profile(company_domain)

            if "error" in data:
                return {"found": False, "platform": "linkedin", "error": data["error"]}

            follower_count = data.get("follower_count", 0)

            return {
                "found": True,
                "platform": "linkedin",
                "linkedin_url": data.get("linkedin_internal_id"),
                "follower_count": follower_count,
                "employee_count": data.get("company_size_on_linkedin", 0),
                "industry": data.get("industry"),
                "specialities": data.get("specialities", []),
                "is_hiring": bool(data.get("hiring_state")),
                "signal_strength": (
                    "strong" if follower_count >= 5000
                    else "moderate" if follower_count >= 500
                    else "weak"
                ),
            }
        except Exception as e:
            logger.warning(f"[SocialSignals] LinkedIn failed: {e}")
            return {"found": False, "platform": "linkedin", "error": str(e)}

    # ─── YouTube Signals ──────────────────────────────────────────────

    async def _youtube_signals(self, youtube_url: str) -> dict:
        """Scrape YouTube channel for subscriber count and video activity."""
        try:
            scraper_key = os.getenv("SCRAPER_API_KEY")
            if not scraper_key:
                return {"found": False, "platform": "youtube"}

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    "http://api.scraperapi.com",
                    params={
                        "api_key": scraper_key,
                        "url": youtube_url,
                        "render": "false",
                    },
                )

            if resp.status_code != 200:
                return {"found": False, "platform": "youtube"}

            html = resp.text
            subscribers = 0
            sub_match = re.search(r'(\d[\d.]*[KMB]?)\s*subscribers', html, re.IGNORECASE)
            if sub_match:
                subscribers = self._parse_count(sub_match.group(1))

            return {
                "found": True,
                "platform": "youtube",
                "url": youtube_url,
                "subscribers": subscribers,
                "signal_strength": "strong" if subscribers >= 10000 else "moderate" if subscribers >= 1000 else "weak",
            }
        except Exception as e:
            return {"found": False, "platform": "youtube", "error": str(e)}

    # ─── Helpers ──────────────────────────────────────────────────────

    def _find_youtube(self, website_data: Optional[dict], company_name: str) -> Optional[str]:
        """Try to find YouTube channel URL from website data."""
        if website_data:
            text = str(website_data)
            yt_match = re.search(r'https?://(?:www\.)?youtube\.com/(?:c/|channel/|@)[\w-]+', text)
            if yt_match:
                return yt_match.group(0)
        return None

    def _parse_count(self, count_str: str) -> int:
        """Parse counts like '1.2K', '3.5M', '500'."""
        count_str = count_str.strip().upper()
        multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}
        for suffix, mult in multipliers.items():
            if count_str.endswith(suffix):
                return int(float(count_str[:-1]) * mult)
        try:
            return int(float(count_str))
        except ValueError:
            return 0

    def _compute_score(self, results: dict) -> dict:
        """Compute composite social presence score."""
        total = 0
        max_score = 0
        breakdown = {}

        # GitHub: 0-25
        gh = results.get("github", {})
        if gh.get("found"):
            strength = gh.get("signal_strength", "none")
            score = {"strong": 25, "moderate": 15, "weak": 5, "none": 0}.get(strength, 0)
            total += score
            breakdown["github"] = score
        max_score += 25

        # Twitter: 0-25
        tw = results.get("twitter", {})
        if tw.get("found"):
            strength = tw.get("signal_strength", "none")
            score = {"strong": 25, "moderate": 15, "weak": 5}.get(strength, 0)
            total += score
            breakdown["twitter"] = score
        max_score += 25

        # LinkedIn: 0-30
        li = results.get("linkedin", {})
        if li.get("found"):
            strength = li.get("signal_strength", "none")
            score = {"strong": 30, "moderate": 18, "weak": 5}.get(strength, 0)
            total += score
            breakdown["linkedin"] = score
        max_score += 30

        # YouTube: 0-20
        yt = results.get("youtube", {})
        if yt.get("found"):
            strength = yt.get("signal_strength", "none")
            score = {"strong": 20, "moderate": 12, "weak": 3}.get(strength, 0)
            total += score
            breakdown["youtube"] = score
        max_score += 20

        return {
            "total": total,
            "max": max_score,
            "percentage": round(total / max_score * 100) if max_score > 0 else 0,
            "breakdown": breakdown,
            "overall_strength": (
                "strong" if total >= 60 else "moderate" if total >= 30 else "weak"
            ),
        }
