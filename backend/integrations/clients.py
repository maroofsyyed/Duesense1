import httpx
import os
from dotenv import load_dotenv

load_dotenv()


class GitHubClient:
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.token = os.environ.get("GITHUB_TOKEN")
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def find_organization(self, company_name: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}/search/users",
                headers=self.headers,
                params={"q": f"{company_name} type:org", "per_page": 5},
            )
            if response.status_code != 200:
                return {"error": f"GitHub API error: {response.status_code}"}
            data = response.json()
            if data.get("total_count", 0) == 0:
                return {"found": False, "message": "No GitHub organization found"}

            org = data["items"][0]
            org_response = await client.get(
                f"{self.base_url}/orgs/{org['login']}", headers=self.headers
            )
            if org_response.status_code == 200:
                org_data = org_response.json()
                return {
                    "found": True,
                    "login": org_data.get("login"),
                    "name": org_data.get("name"),
                    "description": org_data.get("description"),
                    "public_repos": org_data.get("public_repos", 0),
                    "followers": org_data.get("followers", 0),
                    "blog": org_data.get("blog"),
                    "html_url": org_data.get("html_url"),
                    "created_at": org_data.get("created_at"),
                }
            return {"found": True, "login": org["login"], "html_url": org.get("html_url")}

    async def analyze_repositories(self, org_login: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}/orgs/{org_login}/repos",
                headers=self.headers,
                params={"per_page": 30, "sort": "updated"},
            )
            if response.status_code != 200:
                return {"error": f"Could not fetch repos: {response.status_code}"}

            repos = response.json()
            languages = {}
            total_stars = 0
            total_forks = 0
            recent_repos = []

            for repo in repos:
                total_stars += repo.get("stargazers_count", 0)
                total_forks += repo.get("forks_count", 0)
                lang = repo.get("language")
                if lang:
                    languages[lang] = languages.get(lang, 0) + 1
                recent_repos.append({
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": lang,
                    "updated_at": repo.get("updated_at"),
                })

            recent_repos.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

            return {
                "total_repos": len(repos),
                "total_stars": total_stars,
                "total_forks": total_forks,
                "languages": languages,
                "tech_stack": list(languages.keys()),
                "recent_repos": recent_repos[:5],
                "engineering_velocity": "high" if len(repos) > 10 else "medium" if len(repos) > 3 else "low",
            }


class NewsClient:
    def __init__(self):
        self.api_key = os.environ.get("NEWS_API_KEY")
        self.base_url = "https://newsapi.org/v2"

    async def search_company_news(self, company_name: str) -> dict:
        from datetime import datetime, timedelta
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}/everything",
                params={
                    "q": f'"{company_name}"',
                    "from": from_date,
                    "sortBy": "relevancy",
                    "language": "en",
                    "apiKey": self.api_key,
                    "pageSize": 10,
                },
            )
            if response.status_code != 200:
                return {"articles": [], "error": f"News API error: {response.status_code}"}

            data = response.json()
            articles = []
            for a in data.get("articles", []):
                sentiment = _simple_sentiment(
                    (a.get("title") or "") + " " + (a.get("description") or "")
                )
                articles.append({
                    "title": a.get("title"),
                    "description": a.get("description"),
                    "url": a.get("url"),
                    "source": a.get("source", {}).get("name"),
                    "published_at": a.get("publishedAt"),
                    "sentiment": sentiment,
                })
            return {"articles": articles, "total": len(articles)}


class SerpClient:
    def __init__(self):
        self.api_key = os.environ.get("SERPAPI_KEY")

    async def find_competitors(self, company_name: str, description: str = "") -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            queries = [f"{company_name} competitors", f"alternatives to {company_name}"]
            all_results = []

            for query in queries:
                try:
                    response = await client.get(
                        "https://serpapi.com/search",
                        params={
                            "q": query,
                            "api_key": self.api_key,
                            "engine": "google",
                            "num": 10,
                        },
                    )
                    if response.status_code == 200:
                        data = response.json()
                        for r in data.get("organic_results", []):
                            all_results.append({
                                "title": r.get("title"),
                                "url": r.get("link"),
                                "snippet": r.get("snippet"),
                                "source_query": query,
                            })
                except Exception:
                    continue

            # Deduplicate
            seen = set()
            unique = []
            for r in all_results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    unique.append(r)

            return {"competitors": unique[:10], "total_found": len(unique)}

    async def search_market(self, industry: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q": f"{industry} market size growth",
                        "api_key": self.api_key,
                        "engine": "google",
                        "num": 5,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "results": [
                            {"title": r.get("title"), "url": r.get("link"), "snippet": r.get("snippet")}
                            for r in data.get("organic_results", [])[:5]
                        ]
                    }
            except Exception:
                pass
            return {"results": []}


class ScraperClient:
    def __init__(self):
        self.api_key = os.environ.get("SCRAPER_API_KEY")

    async def scrape_website(self, url: str) -> dict:
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    "http://api.scraperapi.com",
                    params={"api_key": self.api_key, "url": url, "render": "false"},
                )
                if response.status_code != 200:
                    return {"error": f"Scraper error: {response.status_code}"}

                soup = BeautifulSoup(response.text, "html.parser")
                meta_desc = ""
                meta = soup.find("meta", attrs={"name": "description"})
                if meta:
                    meta_desc = meta.get("content", "")

                return {
                    "title": soup.title.string if soup.title else "",
                    "meta_description": meta_desc,
                    "headings": {
                        "h1": [h.get_text(strip=True) for h in soup.find_all("h1")][:5],
                        "h2": [h.get_text(strip=True) for h in soup.find_all("h2")][:10],
                    },
                    "text_content": soup.get_text(separator="\n", strip=True)[:3000],
                    "has_pricing": bool(soup.find(string=lambda t: t and "pricing" in t.lower())),
                    "has_careers": bool(soup.find(string=lambda t: t and "careers" in t.lower())),
                }
            except Exception as e:
                return {"error": str(e)}


class EnrichlyrClient:
    """
    Primary enrichment API client for DueSense v2.0.

    Covers: LinkedIn profiles, funding history, web traffic, social signals.
    All methods return {} or {"error": ...} on failure — never raise.
    """

    BASE_URL = "https://api.enrichlayer.com"

    def __init__(self):
        self.api_key = os.environ.get("ENRICHLAYER_API_KEY")
        self.base_url = self.BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        } if self.api_key else {}
        self.timeout = 20.0

    # ── Generic helpers ───────────────────────────────────────────────────

    async def _get(self, path: str, params: dict = None) -> dict:
        """Generic GET with error handling for 404/429."""
        if not self.api_key:
            return {"error": "ENRICHLAYER_API_KEY not configured"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.get(
                    f"{self.base_url}{path}",
                    headers=self.headers,
                    params=params or {},
                )
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 404:
                    return {"found": False, "status": 404}
                elif r.status_code == 429:
                    return {"error": "rate_limited", "retry_after": r.headers.get("Retry-After")}
                else:
                    return {"error": f"HTTP {r.status_code}", "body": r.text[:200]}
            except Exception as e:
                return {"error": str(e)}

    async def _post(self, path: str, body: dict) -> dict:
        """Generic POST with error handling."""
        if not self.api_key:
            return {"error": "ENRICHLAYER_API_KEY not configured"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.post(
                    f"{self.base_url}{path}",
                    headers=self.headers,
                    json=body,
                )
                if r.status_code in (200, 201):
                    return r.json()
                return {"error": f"HTTP {r.status_code}", "body": r.text[:200]}
            except Exception as e:
                return {"error": str(e)}

    # ── Company LinkedIn (existing — backward compatible) ─────────────────

    async def get_company_profile(self, domain: str) -> dict:
        """Fetch company profile by domain (resolve → full profile)."""
        resolve_data = await self._get(
            "/api/linkedin/company/resolve",
            params={"company_domain": domain},
        )
        if "error" in resolve_data or resolve_data.get("found") is False:
            return resolve_data if "error" in resolve_data else {
                "error": f"No LinkedIn URL found for {domain}"
            }
        li_url = resolve_data.get("url")
        if not li_url:
            return {"error": f"No LinkedIn URL found for {domain}"}

        return await self._get(
            "/api/linkedin/company",
            params={"url": li_url, "use_cache": "if-present"},
        )

    async def get_company_linkedin(self, company_name: str, website: str = None) -> dict:
        """
        Fetch LinkedIn company profile (spec method).
        Tries by website domain first, then by name search.
        Returns: followers, employee_count, specialties, job_postings
        """
        if website:
            domain = website.replace("https://", "").replace("http://", "").split("/")[0]
            result = await self.get_company_profile(domain)
            if "error" not in result and result.get("found") is not False:
                return result

        # Fallback to name search
        return await self._post("/linkedin/company/search", {"name": company_name})

    # ── Person LinkedIn (existing — backward compatible) ──────────────────

    async def get_person_profile(self, linkedin_url: str) -> dict:
        """Fetch person LinkedIn profile by URL."""
        return await self._get(
            "/api/v2/linkedin",
            params={
                "linkedin_profile_url": linkedin_url,
                "use_cache": "if-present",
                "skills": "include",
                "personal_email": "exclude",
                "personal_contact_number": "exclude",
            },
        )

    async def get_person_linkedin(self, name: str, company: str = None,
                                   linkedin_url: str = None) -> dict:
        """
        Fetch LinkedIn person profile (spec method).
        If linkedin_url provided, uses direct lookup. Otherwise searches by name.
        Returns: positions, education, skills, connections, prior_exits
        """
        if linkedin_url:
            return await self.get_person_profile(linkedin_url)

        return await self._post("/linkedin/person/search", {
            "name": name,
            "current_company": company,
        })

    async def resolve_person(self, first_name: str, company_domain: str) -> dict:
        """Resolve a person to their LinkedIn profile URL."""
        return await self._get(
            "/api/linkedin/profile/resolve",
            params={
                "first_name": first_name,
                "company_domain": company_domain,
                "similarity_checks": "include",
            },
        )

    async def search_employees(self, company_linkedin_url: str, keyword: str) -> dict:
        """Search employees at a company by title keyword."""
        return await self._get(
            "/api/linkedin/company/employees/search",
            params={
                "linkedin_company_profile_url": company_linkedin_url,
                "keyword_regex": keyword,
                "page_size": "2",
            },
        )

    async def get_company_social(self, domain: str) -> dict:
        """Fetch company social signals (followers, employee count, etc.)."""
        profile = await self.get_company_profile(domain)
        if "error" in profile:
            return profile
        return {
            "follower_count": profile.get("follower_count", 0),
            "employee_count": profile.get("company_size_on_linkedin", 0),
            "industry": profile.get("industry"),
            "specialities": profile.get("specialities", []),
            "is_hiring": bool(profile.get("hiring_state")),
            "linkedin_url": profile.get("linkedin_internal_id"),
        }

    # ── Funding History (NEW) ─────────────────────────────────────────────

    async def get_funding_history(self, company_name: str, website: str = None) -> dict:
        """
        Fetch all funding rounds.
        Returns: rounds[], total_raised, investors, post_money_valuations
        """
        params = {"name": company_name}
        if website:
            domain = website.replace("https://", "").replace("http://", "").split("/")[0]
            params["domain"] = domain
        return await self._get("/funding", params=params)

    # ── Web Traffic (NEW) ─────────────────────────────────────────────────

    async def get_web_traffic(self, domain: str) -> dict:
        """
        Fetch web traffic estimates.
        Returns: monthly_visits, sources, keywords, domain_authority
        """
        clean = domain.replace("https://", "").replace("http://", "").split("/")[0]
        return await self._get("/traffic", params={"domain": clean})

    # ── Social Signals (NEW) ──────────────────────────────────────────────

    async def get_social_signals(self, company_name: str, website: str = None) -> dict:
        """
        Fetch social media presence signals.
        Returns: linkedin_followers, twitter_followers, growth rates
        """
        params = {"name": company_name}
        if website:
            params["website"] = website
        return await self._get("/social", params=params)

    # ── Company Search (NEW) ──────────────────────────────────────────────

    async def search_company(self, query: str) -> list:
        """
        Search for company data (used for competitive landscape).
        Returns: list of company profiles
        """
        result = await self._post("/company/search", {"query": query, "limit": 5})
        if isinstance(result, dict) and "error" in result:
            return []
        return result.get("results", result.get("companies", []))


def _simple_sentiment(text: str) -> str:
    text_lower = text.lower()
    pos = ["success", "growth", "raised", "funding", "launch", "partnership", "award", "revenue", "profitable"]
    neg = ["lawsuit", "loss", "layoff", "decline", "controversy", "failure", "shut down", "bankrupt"]
    p = sum(1 for w in pos if w in text_lower)
    n = sum(1 for w in neg if w in text_lower)
    if p > n:
        return "positive"
    elif n > p:
        return "negative"
    return "neutral"
