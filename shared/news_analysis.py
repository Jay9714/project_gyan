from shared.news_utils import fetch_news_rss
from datetime import datetime

# --- HEAVY IMPORTS (Only safe for Astra) ---
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    from textblob import TextBlob
    vader = SentimentIntensityAnalyzer()
    HAS_LIGHT_NLP = True
except ImportError:
    HAS_LIGHT_NLP = False

try:
    import torch
    from transformers import pipeline
    finbert = pipeline("text-classification", model="ProsusAI/finbert", return_all_scores=True)
    HAS_HEAVY_NLP = True
except:
    HAS_HEAVY_NLP = False

def analyze_with_finbert(text):
    if not HAS_HEAVY_NLP: return 0.0
    try:
        preds = finbert(text[:512])
        scores = {p['label']: p['score'] for p in preds[0]}
        return scores.get('positive', 0) - scores.get('negative', 0)
    except: return 0.0

def analyze_with_vader(text):
    if not HAS_LIGHT_NLP: return 0.0
    try:
        v_score = vader.polarity_scores(text)['compound']
        t_score = TextBlob(text).sentiment.polarity
        return (0.6 * v_score) + (0.4 * t_score)
    except: return 0.0

def analyze_news_sentiment(ticker):
    """Calculates sentiment score."""
    items = fetch_news_rss(ticker)
    if not items: return 0.0 
    
    total_score = 0.0
    count = 0
    
    for item in items:
        text = item.get('title', '')
        score = 0.0
        
        if HAS_HEAVY_NLP:
            score = analyze_with_finbert(text)
            if abs(score) > 0.8: score *= 1.5 
        elif HAS_LIGHT_NLP:
            score = analyze_with_vader(text)
            
        # Time Decay
        weight = 1.0
        try:
            pub_dt = datetime.strptime(item['publishedAt'], "%a, %d %b %Y %H:%M:%S %Z")
            age_days = (datetime.utcnow() - pub_dt).total_seconds() / (3600 * 24)
            weight = max(0.2, 1.0 - (age_days / 7.0))
        except: weight = 0.5
            
        total_score += (score * weight)
        count += 1
        
    if count == 0: return 0.0
    final_score = total_score / count
    return round(max(-1.0, min(1.0, final_score)), 2)