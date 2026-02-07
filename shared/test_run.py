import requests
import time
import sys

# Inside the container, we are querying localhost:8000 (itself)
API_URL = "http://localhost:8000"

def test_bot_lifecycle():
    print("🧪 Testing Bot Lifecycle (Internal)...")
    
    # 1. Initial Status
    try:
        res = requests.get(f"{API_URL}/bot/status")
        print(f"Initial Status: {res.json()}")
    except Exception as e:
        print(f"❌ API Down? {e}")
        return

    # 2. Start Bot
    print("\n▶ Starting Bot...")
    res = requests.post(f"{API_URL}/bot/start")
    print(f"Response: {res.json()}")
    
    time.sleep(1)
    
    # 3. Check Status
    res = requests.get(f"{API_URL}/bot/status")
    data = res.json()
    print(f"Status after Start: {data}")
    
    if data.get("active"):
        print("✅ Bot Started Successfully")
    else:
        print("❌ Bot Failed to Start")
        sys.exit(1)

    # 4. Stop Bot
    print("\n⏹ Stopping Bot...")
    res = requests.post(f"{API_URL}/bot/stop")
    print(f"Response: {res.json()}")
    
    time.sleep(1)
    
    # 5. Check Status
    res = requests.get(f"{API_URL}/bot/status")
    data = res.json()
    print(f"Status after Stop: {data}")
    
    if not data.get("active"):
        print("✅ Bot Stopped Successfully")
    else:
        print("❌ Bot Failed to Stop")
        sys.exit(1)

if __name__ == "__main__":
    test_bot_lifecycle()
