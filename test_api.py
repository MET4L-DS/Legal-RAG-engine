import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    print("\nTesting /health...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(response.json())
    except Exception as e:
        print(f"Error: {e}")

def test_query(query: str):
    print(f"\nTesting /api/v1/query with: '{query}'")
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/query",
            json={"query": query, "stream": False},
            timeout=60
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Answer: {data.get('answer')[:200]}...")
            print(f"Intent: {data.get('metadata', {}).get('category')}")
            print(f"Sources: {len(data.get('sources', []))}")
        else:
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_health()
    test_query("What is the procedure for zero FIR?")
