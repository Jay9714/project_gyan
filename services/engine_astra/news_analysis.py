import requests
from xml.etree import ElementTree as ET
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from datetime import datetime

analyzer = SentimentIntensityAnalyzer()

def fetch_news_rss(ticker):
    """Fetches news headlines from Google News RSS (Free)."""
    # Clean ticker: "TCS.NS" -> "TCS stock news"
    query = ticker.replace(".NS", "") + " stock news"
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200: return []
        
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall('.//item')[:20]: # Limit to 20 items
            title = item.find('title').text
            pub = item.find('pubDate').text
            link = item.find('link').text
            items.append({"title": title, "publishedAt": pub, "url": link})
        return items
    except Exception as e:
        print(f"News Error for {ticker}: {e}")
        return []

def analyze_news_sentiment(ticker):
    """
    Returns a score (0-100) based on recent news sentiment.
    50 is Neutral. >70 is Very Positive. <30 is Very Negative.
    """
    items = fetch_news_rss(ticker)
    if not items: return 50.0 # Neutral if no news
    
    scores = []
    now = datetime.utcnow()
    
    for item in items:
        text = item.get('title', '')
        # VADER Compound: -1.0 (Neg) to +1.0 (Pos)
        compound = analyzer.polarity_scores(text)['compound']
        
        # Time Decay: Newer news matters more
        weight = 1.0
        try:
            # Format: "Mon, 25 Nov 2025 10:30:00 GMT"
            pub_dt = datetime.strptime(item['publishedAt'], "%a, %d %b %Y %H:%M:%S %Z")
            age_days = (now - pub_dt).total_seconds() / (3600 * 24)
            # Decay over 7 days
            weight = max(0.2, 1.0 - (age_days / 7.0))
        except:
            weight = 0.5 # Default lower weight if date parsing fails
            
        scores.append(compound * weight)
        
    if not scores: return 50.0
    
    # Weighted Average (-1 to 1)
    avg_score = sum(scores) / len(scores)
    
    # Map -1..1 to 0..100
    # -1 -> 0, 0 -> 50, 1 -> 100
    final_score = (avg_score + 1) * 50
    return round(min(100.0, max(0.0, final_score)), 2)