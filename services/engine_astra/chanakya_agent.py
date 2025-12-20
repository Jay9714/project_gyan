import requests
import json

OLLAMA_URL = "http://ollama:11434/api/generate"
MODEL_NAME = "llama3" # Ensure you pull this model: docker-compose exec ollama ollama pull llama3

def generate_chanakya_reasoning(ticker, verdict, ai_confidence, data_summary):
    """
    Uses Local LLM to generate a professional investment thesis.
    """
    prompt = f"""
    You are Chanakya, a master financial strategist. Write a concise, 3-sentence investment thesis for {ticker}.
    
    Data:
    - Verdict: {verdict}
    - AI Confidence: {ai_confidence*100:.1f}%
    - Sector: {data_summary.get('sector', 'Unknown')} ({data_summary.get('sector_status', 'Neutral')})
    - Trend: {data_summary.get('trend', 'Neutral')}
    - Fundamentals: Quality={data_summary.get('quality', 'Avg')}, Risk={data_summary.get('risk', 'Avg')}
    - AI Target: {data_summary.get('target', 0)}
    
    Style: Professional, direct, actionable. No disclaimers.
    Output format:
    **Thesis:** [Your reasoning]
    **Key Catalyst:** [One main driver]
    """
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        # 30 second timeout to prevent hanging the worker
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['response'].strip()
        else:
            return f"Chanakya is silent (LLM Status: {response.status_code})."
    except Exception as e:
        print(f"LLM Error: {e}")
        return "Chanakya is meditating (Connection Error or Model Loading)."