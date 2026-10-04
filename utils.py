import time

def call_gemini_with_retry(client, prompt, parse_json=False):
    """Call Gemini with exponential backoff. Use for all Gemini calls."""
    import json

    delays = [2, 5, 15]
    for attempt, delay in enumerate(delays):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
            )
            text = response.text.strip()
            if parse_json:
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    text = text.rsplit("```", 1)[0].strip()
                return json.loads(text)
            return text
        except Exception as e:
            if attempt < len(delays) - 1:
                print(f"  Gemini error, retrying in {delay}s... (attempt {attempt + 1}/3)")
                time.sleep(delay)
            else:
                raise e