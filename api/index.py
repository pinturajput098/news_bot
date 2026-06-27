import os
import json
import requests
import feedparser
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")

KEYS = {
    "gemini": os.environ.get("GEMINI_KEY"),
    "groq": os.environ.get("GROQ_KEY"),
    "openrouter": os.environ.get("OPENROUTER_KEY"),
    "mistral": os.environ.get("MISTRAL_KEY"),
    "huggingface": os.environ.get("HF_KEY")
}

KV_URL = "https://kvdb.io/HanuraGlobalBotStore_pintu07/last_link"

def get_last_posted_link():
    try:
        res = requests.get(KV_URL, timeout=5)
        if res.status_code == 200:
            return res.text.strip()
    except Exception as e:
        print(f"Database read failed: {e}")
    return ""

def save_last_posted_link(link):
    try:
        requests.post(KV_URL, data=link, timeout=5)
    except Exception as e:
        print(f"Database write failed: {e}")

# --- TEXT GENERATION ---
def generate_text_ai(prompt):
    if KEYS["gemini"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={KEYS['gemini']}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception:
            pass

    if KEYS["groq"]:
        try:
            url = "https://api.groq.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {KEYS['groq']}", "Content-Type": "application/json"}
            payload = {"model": "llama3-8b-8192", "messages": [{"role": "user", "content": prompt}]}
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content']
        except Exception:
            pass

    return "Summary generation failed."

# --- DYNAMIC IMAGE GENERATION ---
def generate_image_url(title):
    prompt = f"Professional editorial illustration for financial news, stock market theme, hyperrealistic, high resolution, depicting: {title}"
    try:
        encoded_prompt = requests.utils.quote(prompt)
        return f"https://image.pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true"
    except Exception:
        return "https://via.placeholder.com/1024x1024.png?text=Market+News"

# --- MAIN TASK ---
def check_and_post_news():
    feed_url = "https://finance.yahoo.com/news/rss"
    feed = feedparser.parse(feed_url)
    
    if not feed.entries:
        return "No news found."

    latest_entry = feed.entries[0]
    latest_link = latest_entry.link
    
    if latest_link == get_last_posted_link():
        return "No new news found. Skipping."

    title = latest_entry.get('title', 'Market Update')
    description = latest_entry.get('description', latest_entry.get('summary', 'No description available.'))

    # Strict HTML Prompt
    prompt = f"""
    Analyze this financial news:
    Title: {title}
    Description: {description}

    Provide the output exactly in this format for a Telegram post using HTML tags. 
    CRITICAL: Do NOT use markdown symbols like asterisks (*) or underscores (_). Use <b> for bold text.

    🔥 <b>HOT MARKET UPDATE</b> 🔥

    📰 <b>News Summary:</b>
    [Write a concise 2-3 sentence engaging tweet/summary here]

    📊 <b>Market Impact:</b>
    [Explain clearly what asset classes (Gold, Forex, Crypto, Stocks) will be impacted and whether it's Bullish or Bearish]
    """

    final_text = generate_text_ai(prompt)
    image_url = generate_image_url(title)

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "photo": image_url,
        "caption": final_text,
        "parse_mode": "HTML"
    }
    
    tg_res = requests.post(telegram_url, json=payload)
    
    if tg_res.status_code == 200:
        save_last_posted_link(latest_link)
        return "Successfully analyzed and posted new news!"
    else:
        # Emergency Fallback: Agar HTML me fir bhi panga ho, to normal text bhej do
        payload["parse_mode"] = ""
        requests.post(telegram_url, json=payload)
        save_last_posted_link(latest_link)
        return "Posted as plain text due to tag error."

@app.route('/api/index')
def cron_trigger():
    result = check_and_post_news()
    return jsonify({"status": "executed", "result": result})

@app.route('/')
def home():
    return "News Automation Bot is up and running!"

if __name__ == '__main__':
    app.run(debug=True)
