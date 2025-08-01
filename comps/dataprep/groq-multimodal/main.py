import os
import base64
import requests
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ImagePathRequest(BaseModel):
    image_path: str

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

@app.post("/v1")
async def analyze_image(payload: ImagePathRequest):
    image_path = payload.image_path
    base64_image = encode_image_to_base64(image_path)
    data_url = f"data:image/jpeg;base64,{base64_image}"

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": "Bearer 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",
        "Content-Type": "application/json"
    }

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]
        }
    ]
    api_payload = {
        "model": "qwen/qwen-2.5-vl-7b-instruct",
        "messages": messages
    }

    response = requests.post(url, headers=headers, json=api_payload)
    return response.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)