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
