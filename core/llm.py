import os
import re

class LLMClient:
    def __init__(self):
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    def generate(self, prompt):
        if not self.client:
            raise RuntimeError("Gemini API key is missing or the Gemini client could not be initialized.")
        response = self.client.models.generate_content(model=self.model, contents=prompt)
        return response.text or ""

    @staticmethod
    def extract_code(text, language):
        pattern = rf"```{language}\s*(.*?)```"
        m = re.search(pattern, text, flags=re.I | re.S)
        if m:
            return m.group(1).strip()
        m = re.search(r"```\s*(.*?)```", text, flags=re.S)
        return m.group(1).strip() if m else text.strip()
