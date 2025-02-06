import asyncio
import aiohttp
import json
from datetime import datetime
from bs4 import BeautifulSoup


class NewsScraper:
    def __init__(self):
        self.parsers = {"BBC": self.parse_bbc}
        self.targets = [("https://www.bbc.com", "BBC", ["/", "/news", "/sport", "/business", "/innovation", "/culture", "/arts", "/travel", "/future-planet"][:])]

    async def fetch(self, session, url):
        try:
            async with session.get(url, timeout=10) as resp:
                return await resp.text()
        except Exception:
            return ""

    def parse_bbc(self, html):
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.find_all("a", href=True)
        return [
            {"headline": a.get_text(strip=True), "url": f"https://www.bbc.com{a['href']}"}
            for a in articles if "article" in a["href"] and a["href"].startswith("/")
        ]

    async def scrape_headlines(self, session):
        tasks = [self.fetch(session, url + path) for url, site, paths in self.targets for path in paths]
        results = await asyncio.gather(*tasks)
        return [item for sublist in [self.parsers["BBC"](html) for html in results if html] for item in sublist]

    async def fetch_article(self, session, url):
        try:
            async with session.get(url, timeout=10) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                article = soup.find("article") or soup
                return {
                    "headline": (soup.find("meta", property="og:title") or {}).get("content", ""),
                    "thumbnail": (soup.find("meta", property="og:image") or {}).get("content", ""),
                    "article_text": "\n".join(p.text for p in article.find_all("p")),
                    "timestamp": article.find("time")["datetime"] if article.find("time") else datetime.now().isoformat()
                }
        except Exception:
            return {"headline": "Error", "thumbnail": "Error", "article_text": "Error"}

    async def scrape_articles(self, session, urls):
        tasks = [self.fetch_article(session, url) for url in urls]
        print(f"Scraping {len(urls)} articles...", urls)
        return await asyncio.gather(*tasks)

    async def run(self):
        async with aiohttp.ClientSession() as session:
            headlines = await self.scrape_headlines(session)
            urls = list({item["url"] for item in headlines})  # Unique URLs
            articles = await self.scrape_articles(session, urls)
            return [{**h, **a} for h, a in zip(headlines, articles)]

    def save_to_json(self, data, filename="news_output.json"):
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(data)} articles to {filename}")


if __name__ == "__main__":
    scraper = NewsScraper()
    news_data = asyncio.run(scraper.run())
    scraper.save_to_json(news_data)
