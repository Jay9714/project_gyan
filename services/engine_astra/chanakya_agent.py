import requests
import json

# Ensure this matches the service name in docker-compose
OLLAMA_URL = "http://ollama:11434/api/generate"
# Fallback model if specific version fails
MODEL_NAME = "llama3" 

def generate_chanakya_reasoning(ticker, verdict, ai_confidence, data_summary, catalyst_context=None, shap_explanation=None):
    """
    Uses Local LLM to generate a professional investment thesis.
    NOW SUPPORTS: 'catalyst_context' - Strategic info that overrides math.
    """
    
    # 1. Base Prompt
    prompt = f"""
    You are Chanakya, a master financial strategist. Write a concise, 3-sentence investment thesis for {ticker}.
    
    HARD DATA (Quantitative):
    - Math Verdict: {verdict}
    - AI Confidence: {ai_confidence*100:.1f}%
    - Sector: {data_summary.get('sector', 'Unknown')} ({data_summary.get('sector_status', 'Neutral')})
    - Trend: {data_summary.get('trend', 'Neutral')}
    - Fundamentals: Quality={data_summary.get('quality', 'Avg')}, Risk={data_summary.get('risk', 'Avg')}
    - AI Target: {data_summary.get('target', 0)}
    - Local Factors: {shap_explanation if shap_explanation else 'N/A'}
    """

    # 2. INJECT MEGA-CATALYST (Qualitative Override)
    if catalyst_context:
        prompt += f"""
        
        CRITICAL INTELLIGENCE (Override the Math if necessary):
        - Mega-Catalyst: {catalyst_context}
        
        INSTRUCTION: If the 'Mega-Catalyst' implies massive future growth (e.g., huge order book, government policy), 
        you MUST weigh it higher than the short-term technicals. 
        If the math says SELL but the Catalyst says BUY, explain why the Catalyst wins.
        """
    
    prompt += """
    Style: Professional, direct, actionable. No disclaimers.
    Output format:
    **Thesis:** [Your reasoning]
    **Key Catalyst:** [One main driver]
    """
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 100, # Limit output length to be concise
            "temperature": 0.3
        }
    }
    
    try:
        # INCREASED TIMEOUT TO 120 SECONDS
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        
        if response.status_code == 404:
            return "Error: LLM Model 'llama3' not found. Run 'docker-compose exec ollama ollama pull llama3'."
            
        if response.status_code == 200:
            return response.json().get('response', '').strip()
            
        return f"Chanakya is silent (LLM Status: {response.status_code})."
        
    except Exception as e:
        print(f"LLM Error: {e}")
        return f"Chanakya is meditating (Connection Error or Timeout: {str(e)})"