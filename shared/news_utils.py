import requests
from xml.etree import ElementTree as ET
from datetime import datetime

def fetch_news_rss(ticker):
    """Fetches news headlines from Google News RSS (Free)."""
    query = ticker.replace(".NS", "") + " stock news India"
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200: return []
        
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall('.//item')[:15]: 
            title = item.find('title').text
            pub = item.find('pubDate').text
            items.append({"title": title, "publishedAt": pub})
        return items
    except Exception:
        return []   