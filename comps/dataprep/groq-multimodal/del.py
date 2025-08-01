import requests
import json

response = requests.get(
  url="https://openrouter.ai/api/v1/key",
  headers={
    "Authorization": f"Bearer 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"
  }
)

print(json.dumps(response.json(), indent=2))
