import os
import re
import requests
import urllib.parse
from flask import Flask, request, jsonify, send_from_directory
from threading import Lock

# ----------------------------
# Flask app
# ----------------------------
app = Flask(__name__, static_folder='../Frontend')  # Adjust path if needed

# ----------------------------
# 🧠 Conversation history
# ----------------------------
conversation_history = [{"role":"system","content":"You are a Stardew Valley expert. Answer concisely, practically, and focus on actionable steps."}]
history_lock = Lock()

# ----------------------------
# 🔑 Keyword extraction
# ----------------------------
def extract_keywords(text):
    stop_words = ['the','a','an','to','do','i','like','what','how','where','is','in','for','of',
                  'can','me','these','that','this','you']
    words = re.findall(r'\b\w+\b', text.lower())
    keywords = [w for w in words if w not in stop_words]
    return ' '.join(keywords)

# ----------------------------
# 🌐 Wiki retrieval
# ----------------------------
def get_wiki_text(title):
    url = "https://stardewvalleywiki.com/w/api.php"
    headers = {"User-Agent": "stardew-valley-guide-bot"}
    params = {"action":"query","format":"json","prop":"extracts","explaintext":True,"titles":title,"redirects":1}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        pages = data.get('query', {}).get('pages', {})
        for page_id in pages:
            if page_id != "-1":
                return pages[page_id].get('extract', '')
        return None
    except:
        return None

def get_wiki_search_text(question):
    keywords = extract_keywords(question)
    if not keywords:
        return None
    url = "https://stardewvalleywiki.com/w/api.php"
    headers = {"User-Agent": "stardew-valley-guide-bot"}
    params = {"action":"query","format":"json","list":"search","srsearch":keywords,"utf8":1}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        search_results = data.get("query", {}).get("search", [])
        if not search_results:
            return None
        top_title = search_results[0].get("title")
        extract = get_wiki_text(top_title)
        if extract:
            return f"From {top_title}:\n{extract[:1500]}"
        return None
    except:
        return None

# ----------------------------
# 🌐 Reddit retrieval
# ----------------------------
def get_reddit_text(query):
    keywords = extract_keywords(query)
    if not keywords:
        return None
    headers = {"User-Agent": "stardew-valley-guide-bot"}
    url = f"https://www.reddit.com/r/StardewValley/search.json?q={urllib.parse.quote(keywords)}&restrict_sr=1&sort=relevance&t=all"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        posts = data.get("data", {}).get("children", [])
        combined_text = ""
        for post in posts[:5]:
            post_data = post["data"]
            combined_text += post_data.get("title", "") + "\n" + post_data.get("selftext", "") + "\n"
        return combined_text.strip()
    except:
        return None

# ----------------------------
# 🧠 Gemini API call
# ----------------------------
def ask_ai(question):
    wiki_text = get_wiki_search_text(question) or ""
    reddit_text = get_reddit_text(question) or ""
    combined_context = f"Wiki info:\n{wiki_text}\n\nReddit info:\n{reddit_text}"

    with history_lock:
        conversation_history.append({"role":"user","content":question})
        conversation_text = "\n".join([f"{m['role']}: {m['content']}" for m in conversation_history])

    api_key = "AIzaSyDn-Sc5L8tZBJYfDvAJTXwzNk1xVwP2jUU"  # Replace with your key
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type":"application/json","X-goog-api-key":api_key}
    data = {"contents":[{"parts":[{"text":f"Use the following context to answer concisely with practical advice for Stardew Valley:\n{combined_context}\n\nConversation:\n{conversation_text}\n\nQuestion: {question}"}]}]}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=25)
        response.raise_for_status()
        json_resp = response.json()
        text_parts = json_resp["candidates"][0]["content"]["parts"]
        answer = " ".join([part["text"] for part in text_parts]).strip()
    except:
        answer = "Sorry, I couldn't get an answer from Gemini."

    with history_lock:
        conversation_history.append({"role":"assistant","content":answer})

    return answer

# ----------------------------
# Flask routes
# ----------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.json
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400
    answer = ask_ai(question)
    return jsonify({"answer": answer})

# ----------------------------
# Run app
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
