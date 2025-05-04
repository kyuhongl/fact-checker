def format_prompt(text):
    return f"""
Evaluate this claim:
\"\"\"{text}\"\"\"

Output:
1. Verdict (True/False/Misleading/Unclear)
2. 1-3 sentence explanation
3. At least 2 reputable sources with URLs
4. Historical context (if applicable)
5. Classification: (political, science, medicine, etc.)
"""
