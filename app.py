from flask import Flask, request, jsonify
from flask_cors import CORS
from prompts import format_prompt
from dotenv import load_dotenv
import anthropic
import os

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
app = Flask(__name__)
CORS(app) 


@app.route("/factcheck", methods=["POST"])
def factcheck():
    text = request.json["text"]
    prompt = format_prompt(text)

    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=800,
        temperature=0.3,
        system="You are a meticulous, unbiased fact-checking assistant.",
        messages=[{"role": "user", "content": prompt}]
    )

    structured = parse_claude_response(response.content)
    return jsonify(structured)

def parse_claude_response(text):
    # Parse response into: verdict, justification, sources[], context
    # You can use regex or Claude’s own formatting
    return {
        "verdict": "...",
        "justification": "...",
        "sources": [{"title": "Example", "url": "https://reuters.com/..."}, ...],
        "context": "...",
        "confidence": 78  # Calculate using source_data.js logic
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

