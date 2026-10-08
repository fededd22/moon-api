"""مثال عميل (للمطوّر): يستدعي Moon API مباشرة."""
import httpx

API_URL = "http://localhost:8000"
API_KEY = "moon_xxxxxxxx"

r = httpx.post(f"{API_URL}/api/run", headers={"X-API-Key": API_KEY},
               json={"function": "secret_formula", "args": [5, 3]}, timeout=60)
print(r.json())
