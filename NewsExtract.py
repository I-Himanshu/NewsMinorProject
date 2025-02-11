import asyncio
import aiohttp
import json
from datetime import datetime
from bs4 import BeautifulSoup
from Summarizer import preprocess_text, generate_summary
import random

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
                    "timestamp": article.find("time")["datetime"] if article.find("time") else datetime.now().isoformat(),
                    "summary": generate_summary(article.get_text()),
                    "keywords": [tag.get_text() for tag in article.find("div", {"data-component": "tags"}).find("div").find_all("a")] if article.find("div", {"data-component": "tags"}) else [],
                    "author": article.find("div", {"data-testid": "byline-new-contributors"}).find_all("span")[0].get_text() if article.find("div", {"data-testid": "byline-new-contributors"}) else "",
                    "source": article.find("div", {"data-testid": "byline-new-contributors"}).find_all("span")[1].get_text() if article.find("div", {"data-testid": "byline-new-contributors"}) else "",
                }
        except Exception:
            return {"headline": "Error", "thumbnail": "Error", "article_text": "Error"}

    async def scrape_articles(self, session, urls):
        tasks = [self.fetch_article(session, url) for url in urls[:]]
        print(f"Scraping {len(urls)} articles...")
        return await asyncio.gather(*tasks)

    async def run(self):
        async with aiohttp.ClientSession() as session:
            headlines = await self.scrape_headlines(session)
            urls = list({item["url"] for item in headlines})  # Unique URLs
            articles = await self.scrape_articles(session, urls)
            return [{**h, **a} for h, a in zip(headlines, articles)]

    def save_to_json(self, data, filename="news_output.json"):
        with open(filename, "r") as f:
            old_data = json.load(f)
        count = 0
        for key, value in data.items():
            if key not in old_data:
                old_data[key] = value
                count += 1
        print("Sorting News by timestamp...")
        old_data = {
            k: v for k, v in sorted(
                old_data.items(),
                key=lambda item: datetime.fromisoformat(
                    item[1].get("timestamp", "2000-01-01T00:00:00")
                ).replace(tzinfo=None),  # Remove timezone info
                reverse=True
            )
        }
        # Remove Error articles
        old_data = {k: v for k, v in old_data.items() if v["headline"] != "Error"}

        # Save 200 latest news to latest_news.json
        latest_news = {k: v for k, v in list(old_data.items())[:200]}
        latest_keys = list(latest_news.keys()) 
        # Randomly shuffle the keys
        random.shuffle(latest_keys)
        latest_news = {k: latest_news[k] for k in latest_keys}
        with open("latest_news.json", "w") as f:
            json.dump(latest_news, f, indent=4)
        with open(filename, "w") as f:
            json.dump(old_data, f, indent=4)
        print("News saved to news_output.json, Total news:", len(old_data), "New news:", count)


if __name__ == "__main__":
    scraper = NewsScraper()
    news_data = asyncio.run(scraper.run())
    news_data = {item["url"]: item for item in news_data}
    scraper.save_to_json(news_data)
