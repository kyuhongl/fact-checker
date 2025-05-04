from flask import Flask, request, jsonify
from flask_cors import CORS
from prompts import format_prompt
from dotenv import load_dotenv
import anthropic
import os
import re

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
app = Flask(__name__)
CORS(app) 

# For debugging
@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Fact-checker API is running"})

@app.route("/factcheck", methods=["POST"])
def factcheck():
    try:
        if not os.getenv("CLAUDE_API_KEY"):
            return jsonify({"error": "Claude API key is not configured"}), 500
            
        text = request.json["text"]
        if not text or len(text) < 3:
            return jsonify({"error": "Text too short"}), 400
            
        print(f"Received request with text: {text[:50]}...")  # Log the first 50 chars
        
        prompt = format_prompt(text)
        print(f"Generated prompt, sending to Claude...")
        
        # Use a more stable model identifier
        model = "claude-3-sonnet-20240229"
        try:
            response = client.messages.create(
                model=model,
                max_tokens=800,
                temperature=0.3,
                system="You are a meticulous, unbiased fact-checking assistant.",
                messages=[{"role": "user", "content": prompt}]
            )
        except Exception as model_error:
            print(f"Error with model {model}: {model_error}")
            # Fallback to older Claude model
            model = "claude-2.1"
            response = client.messages.create(
                model=model,
                max_tokens=800,
                temperature=0.3,
                system="You are a meticulous, unbiased fact-checking assistant.",
                messages=[{"role": "user", "content": prompt}]
            )
        
        # Print the full raw response from Claude
        print("\n===== CLAUDE RAW RESPONSE =====")
        print(response.content)
        print("===== END CLAUDE RESPONSE =====\n")
        
        structured = parse_claude_response(response.content)
        print("\n===== STRUCTURED RESPONSE =====")
        print(structured)
        print("===== END STRUCTURED RESPONSE =====\n")
        
        return jsonify(structured)
    except Exception as e:
        import traceback
        print(f"Error in factcheck endpoint: {e}")
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

