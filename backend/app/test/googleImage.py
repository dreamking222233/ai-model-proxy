"""Local manual test helper for Gemini image generation.

Do not hardcode API keys here. Use a server-side channel configuration instead.
"""

import os

from google import genai


api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("Set GOOGLE_API_KEY before running this manual test")

client = genai.Client(api_key=api_key)

prompt = "生成一张一位程序员在咖啡厅里认真使用 claude code 编程的场景"
response = client.models.generate_content(
 model="gemini-2.5-flash-image",
 contents=[prompt],
)

for index, part in enumerate(response.parts, start=1):
    if part.text is not None:
        print(part.text)
    elif part.inline_data is not None:
        with open(f"generated_image_{index}.png", "wb") as f:
            f.write(part.inline_data.data)
