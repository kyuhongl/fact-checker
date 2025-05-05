def format_prompt(text):
    return f"""
Evaluate this claim:
\"\"\"{text}\"\"\"

Please respond in a strictly structured format:
1. Verdict: (Only use one of these exact words: True, False, Misleading, or Unclear)
2. Explanation: (1-3 sentences explaining your verdict)
3. Sources: (At least 2 reputable sources with full URLs, each on a new line)
4. Historical context: (if applicable)
5. Classification: (political, science, medicine, etc.)

Important: Always follow this exact format with numbered points.
"""
