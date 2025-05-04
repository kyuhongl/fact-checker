from flask import Flask, request, jsonify
from flask_cors import CORS
from prompts import format_prompt
from dotenv import load_dotenv
import anthropic
import os
import re
import sys
import io
import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)
print("== Fact-checker backend started with immediate log flushing ==")

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
app = Flask(__name__)
CORS(app) 

# For debugging
@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Fact-checker API is running"})

recent_responses = []  # Store recent responses for debugging

@app.route("/debug-responses", methods=["GET"])
def debug_responses():
    """Endpoint to view the most recent Claude responses"""
    return jsonify(recent_responses)

@app.route("/factcheck", methods=["POST"])
def factcheck():
    try:
        if not os.getenv("CLAUDE_API_KEY"):
            print("ERROR: Claude API key is not configured!")
            return jsonify({"error": "Claude API key is not configured"}), 500
            
        text = request.json["text"]
        if not text or len(text) < 3:
            print("ERROR: Text too short")
            return jsonify({"error": "Text too short"}), 400
            
        print(f"== Received request with text: {text[:100]}...")
        
        prompt = format_prompt(text)
        print(f"== Generated prompt:")
        print(prompt)
        print("== Sending to Claude...")
        
        # Use the specified model
        model = "claude-3-7-sonnet-20250219"
        try:
            print(f"== Making API call to Claude with model: {model}")
            response = client.messages.create(
                model=model,
                max_tokens=800,
                temperature=0.3,
                system="You are a meticulous, unbiased fact-checking assistant.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            print("\n==========================================")
            print("==== CLAUDE RAW RESPONSE START ====")
            print(response.content)
            print("==== CLAUDE RAW RESPONSE END ====")
            print("==========================================\n")
            
            structured = parse_claude_response(response.content)
            print("\n== STRUCTURED RESPONSE:")
            import json
            print(json.dumps(structured, indent=2))
            
            # Store response for debugging (limit to last 5)
            if len(recent_responses) >= 5:
                recent_responses.pop(0)
            recent_responses.append({
                "text": text[:100] + "...",
                "timestamp": datetime.datetime.now().isoformat(),
                "claude_response": response.content,
                "structured": structured
            })
            
            return jsonify(structured)
        except Exception as claude_error:
            print(f"ERROR with Claude API call: {claude_error}")
            raise claude_error
            
    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR in factcheck endpoint: {e}")
        print("== TRACEBACK:")
        print(traceback.format_exc())
        return jsonify({
            "error": str(e),
            "verdict": "Error",
            "justification": "The fact-checking service encountered an error. Please try again.",
            "sources": [{"title": "Error", "url": "#"}],
            "context": "Service unavailable",
            "confidence": 0
        }), 500

def parse_claude_response(text):
    # More robust parsing
    verdict = "Unverified"
    justification = "Unable to process response"
    sources = []
    context = ""
    
    try:
        # Look for verdict
        verdict_match = re.search(r"1\.\s*Verdict:?\s*([A-Za-z]+)", text)
        if verdict_match:
            verdict = verdict_match.group(1).strip()
        
        # Look for explanation
        explanation_match = re.search(r"2\.[^\n]*(explanation|sentences?)[^\n]*\n+(.*?)(?=\n+\d\.|\Z)", text, re.DOTALL)
        if explanation_match:
            justification = explanation_match.group(2).strip()
        
        # Look for sources
        sources_section = re.search(r"3\.[^\n]*(sources|reputable)[^\n]*\n+(.*?)(?=\n+\d\.|\Z)", text, re.DOTALL)
        if sources_section:
            source_text = sources_section.group(2)
            url_matches = re.finditer(r"(.*?)?(https?://\S+)", source_text)
            
            for match in url_matches:
                title = match.group(1).strip() if match.group(1) else "Source"
                url = match.group(2).strip()
                # Clean up title
                title = re.sub(r"^[-*•]", "", title).strip()
                if not title:
                    title = "Source"
                sources.append({"title": title, "url": url})
        
        # Look for context
        context_match = re.search(r"4\.[^\n]*(context|historical)[^\n]*\n+(.*?)(?=\n+\d\.|\Z)", text, re.DOTALL)
        if context_match:
            context = context_match.group(2).strip()

        # If still empty, use simpler parsing
        if not justification:
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if line.strip() and "verdict" not in line.lower() and i > 1:
                    justification = line.strip()
                    break
    
    except Exception as e:
        print(f"Error parsing Claude response: {e}")
    
    # Ensure we have some reasonable values
    if not sources:
        sources = [{"title": "No sources found", "url": "#"}]
    
    # Confidence calculation - simple for now
    confidence = 75 if verdict.lower() in ["true", "false"] else 50
    if not context:
        context = "No additional context provided"
    
    return {
        "verdict": verdict,
        "justification": justification,
        "sources": sources,
        "context": context,
        "confidence": confidence
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

