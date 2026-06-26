import requests
import json

base_url = "http://127.0.0.1:8000"

# 1. Login
print("Logging in...")
login_response = requests.post(
    f"{base_url}/api/v1/auth/login",
    json={"email": "user@example.com", "password": "password123"}
)

if login_response.status_code != 200:
    print(f"Login failed: {login_response.text}")
    exit(1)

token = login_response.json().get("access_token")
print("Login successful. Token acquired.")

# 2. Chat
print("Sending test message...")
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}
payload = {
    "message": "What is AI?",
    "history": []
}

chat_response = requests.post(
    f"{base_url}/chat",
    headers=headers,
    json=payload
)

if chat_response.status_code == 200:
    print("\n--- Chatbot Response ---")
    print(chat_response.json().get("response"))
else:
    print(f"Chat request failed: {chat_response.text}")
