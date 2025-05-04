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
                system="You are a cutting-edge, meticulous fact-checking assistant for 2025+. Evaluate claims using current information sources, identify synthetic media, detect AI-generated content, and assess information from emerging platforms. Provide verdicts (True/False/Misleading/Unclear) with verifiable evidence, specify source credibility metrics, include full URLs, and acknowledge data recency limitations. Maintain strict neutrality across political and cultural divides while recognizing evolving consensus on scientific topics.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            print("\n==========================================")
            print("==== CLAUDE RAW RESPONSE START ====")
            print(response.content)
            print("==== CLAUDE RAW RESPONSE END ====")
            print("==========================================\n")
            
            # Extract text from response content if it's a list of TextBlock objects
            response_text = ""
            if isinstance(response.content, list):
                for block in response.content:
                    if hasattr(block, 'text'):
                        response_text += block.text
            else:
                response_text = response.content
            
            structured = parse_claude_response(response_text)
            print("\n== STRUCTURED RESPONSE:")
            import json
            print(json.dumps(structured, indent=2))
            
            # Store response for debugging (limit to last 5)
            if len(recent_responses) >= 5:
                recent_responses.pop(0)
            recent_responses.append({
                "text": text[:100] + "...",
                "timestamp": datetime.datetime.now().isoformat(),
                "claude_response": response_text,  # Store the extracted text
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
    """Parse Claude's response into structured data"""
    print("\n== RAW TEXT TO PARSE ==")
    print(text)
    
    # Default values
    verdict = "Unverified"
    justification = "Unable to process response"
    sources = []
    context = "No additional context provided"
    confidence = 50
    
    try:
        # First try to find the verdict
        verdict_patterns = [
            r"Verdict:?\s*(True|False|Misleading|Unclear|Verified|Unverified)",
            r"1\..*?(True|False|Misleading|Unclear|Verified|Unverified)",
        ]
        
        for pattern in verdict_patterns:
            verdict_match = re.search(pattern, text, re.IGNORECASE)
            if verdict_match:
                verdict = verdict_match.group(1).strip()
                break
        
        # Look for explanation
        justification_patterns = [
            r"2\.(.*?)(?=3\.|$)",
            r"explanation:(.*?)(?=3\.|$)",
            r"justification:(.*?)(?=3\.|$)",
        ]
        
        for pattern in justification_patterns:
            explanation_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if explanation_match:
                justification = explanation_match.group(1).strip()
                # Remove numbering and labels
                justification = re.sub(r"^[0-9]+\.?\s*", "", justification)
                justification = re.sub(r"explanation:?", "", justification, flags=re.IGNORECASE).strip()
                break
        
        # If we couldn't find a structured explanation, take the first paragraph after the verdict
        if justification == "Unable to process response":
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if any(keyword in line.lower() for keyword in ["verdict", "true", "false", "misleading", "unclear"]):
                    # Take the next non-empty line as justification
                    for j in range(i+1, min(i+5, len(lines))):
                        if lines[j].strip() and not any(keyword in lines[j].lower() for keyword in ["source", "context", "classification"]):
                            justification = lines[j].strip()
                            break
                    break
        
        # Look for sources
        sources_section = ""
        sources_patterns = [
            r"3\.(.*?)(?=4\.|$)",
            r"sources:(.*?)(?=4\.|$)",
        ]
        
        for pattern in sources_patterns:
            sources_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if sources_match:
                sources_section = sources_match.group(1).strip()
                break
        
        if sources_section:
            # Look for URLs
            url_matches = re.finditer(r"(.*?)(https?://\S+)", sources_section)
            
            for match in url_matches:
                title = match.group(1).strip()
                url = match.group(2).strip()
                
                # Clean up title
                title = re.sub(r"^[-*•]", "", title).strip()
                if not title:
                    title = "Source"
                
                sources.append({"title": title, "url": url})
            
            # If no URLs found but there's content, add it as text
            if not sources and sources_section:
                # Split by lines or bullet points
                source_lines = re.split(r'[\n•*-]', sources_section)
                for line in source_lines:
                    line = line.strip()
                    if line and not line.lower().startswith(('source', '3.')):
                        sources.append({"title": line, "url": "#"})
        
        # Look for context
        context_patterns = [
            r"4\.(.*?)(?=5\.|$)",
            r"historical context:(.*?)(?=5\.|$)",
            r"context:(.*?)(?=5\.|$)",
        ]
        
        for pattern in context_patterns:
            context_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if context_match:
                context = context_match.group(1).strip()
                # Remove numbering and labels
                context = re.sub(r"^[0-9]+\.?\s*", "", context)
                context = re.sub(r"(historical )?context:?", "", context, flags=re.IGNORECASE).strip()
                break
        
        # Calculate confidence based on verdict clarity
        if verdict.lower() in ["true", "false", "verified"]:
            confidence = 80
        elif verdict.lower() in ["misleading"]:
            confidence = 60
        elif verdict.lower() in ["unclear", "unverified"]:
            confidence = 50
        
    except Exception as e:
        print(f"Error parsing Claude response: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Ensure we have some reasonable values
    if not sources:
        sources = [{"title": "No sources found", "url": "#"}]
    
    if not context:
        context = "No additional context provided"
    
    result = {
        "verdict": verdict,
        "justification": justification,
        "sources": sources,
        "context": context,
        "confidence": confidence
    }
    
    print("\n== PARSED RESULT ==")
    print(result)
    
    return result

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

