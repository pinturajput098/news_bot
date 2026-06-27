import os
import json
import requests
import feedparser
from flask import Flask, jsonify
from dotenv import load_dotenv

# .env file se keys load karne ke liye
load_dotenv()

app = Flask(__name__)

# Environment Variables se credentials uthana
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")

# AI Keys Backup Fallback Chain
KEYS = {
    "gemini": os.environ.get("GEMINI_KEY"),
    "groq": os.environ.get("GROQ_KEY"),
    "openrouter": os.environ.get("OPENROUTER_KEY"),
    "mistral": os.environ.get("MISTRAL_KEY"),
    "huggingface": os.environ.get("HF_KEY")
}

def get_last_posted_link():
    try:
        if os.path.exists("last_link.txt"):
            with open("last_link.txt", "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""

def save_last_posted_link(link):
    try:
        with open("last_link.txt", "w") as f:
            f.write(link)
    except Exception:
        pass

# --- TEXT GENERATION FALLBACK LOGIC ---
def generate_text_ai(prompt):
    # Fallback 1: Gemini 2.5 Flash
    if KEYS["gemini"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={KEYS['gemini']}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"Gemini failed: {e}")

    # Fallback 2: Groq (Llama3)
    if KEYS["groq"]:
        try:
            url = "https://api.groq.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {KEYS['groq']}", "Content-Type": "application/json"}
            payload = {
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": prompt}]
            }
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"Groq failed: {e}")

    # Fallback 3: OpenRouter
    if KEYS["openrouter"]:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {KEYS['openrouter']}", "Content-Type": "application/json"}
            payload = {
                "model": "google/gemini-2.5-flash",
                "messages": [{"role": "user", "content": prompt}]
            }
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"OpenRouter failed: {e}")

    return "Summary generation failed across all AI models."

# --- IMAGE GENERATION FALLBACK LOGIC ---
def generate_image_url(prompt):
    try:
        encoded_prompt = requests.utils.quote(prompt)
        img_url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true"
        res = requests.head(img_url, timeout=10)
        if res.status_code == 200:
            return img_url
    except Exception as e:
        print(f"Pollinations AI failed: {e}")

    if KEYS["huggingface"]:
        try:
            url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
            headers = {"Authorization": f"Bearer {KEYS['huggingface']}"}
            res = requests.post(url, json={"inputs": prompt}, headers=headers, timeout=15)
            if res.status_code == 200:
                return f"https://image.pollinations.ai/p/{requests.utils.quote(prompt)}"
        except Exception as e:
            print(f"HuggingFace failed: {e}")

    return "https://via.placeholder.com/1024x1024.png?text=Market+News+Update"

# --- MAIN TASK ---
def check_and_post_news():
    feed_url = "https://finance.yahoo.com/news/rss"
    feed = feedparser.parse(feed_url)
    
    if not feed.entries:
        return "No news found in feed."

    latest_entry = feed.entries[0]
    latest_link = latest_entry.link
    
    if latest_link == get_last_posted_link():
        return "No new news found. Skipping."

    # BUG FIXED HERE: get() method handles missing description safely
    title = latest_entry.get('title', 'Market Update')
    description = latest_entry.get('description', latest_entry.get('summary', 'No description available.'))

    prompt = f"""
    Analyze this financial news:
    Title: {title}
    Description: {description}

    Provide the output exactly in this format for a Telegram post:
    🔥 *HOT MARKET UPDATE* 🔥

    📰 *News Summary:*
    [Write a concise 2-3 sentence engaging tweet/summary here]

    📊 *Market Impact:*
    [Explain clearly what asset classes (Gold, Forex, Crypto, Stocks) will be impacted and whether it's Bullish or Bearish]
    """

    final_text = generate_text_ai(prompt)
    img_prompt = f"Financial market charts showing dramatic impact, professional trading background, realistic, corporate style, representing: {title}"
    image_url = generate_image_url(img_prompt)

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "photo": image_url,
        "caption": final_text,
        "parse_mode": "Markdown"
    }
    
    tg_res = requests.post(telegram_url, json=payload)
    
    if tg_res.status_code == 200:
        save_last_posted_link(latest_link)
        return "Successfully analyzed and posted new news!"
    else:
        return f"Failed to post to Telegram: {tg_res.text}"

@app.route('/api/index')
def cron_trigger():
    result = check_and_post_news()
    return jsonify({"status": "executed", "result": result})

@app.route('/')
def home():
    return "News Automation Bot is up and running!"

if __name__ == '__main__':
    app.run(debug=True)
