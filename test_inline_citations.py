import json
import urllib.request

url = "http://localhost:8000/api/v1/query"
data = {
    "query": "What is the punishment for theft?",
    "stream": False
}

headers = {"Content-Type": "application/json"}
req = urllib.request.Request(url, json.dumps(data).encode('utf-8'), headers)

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        print(json.dumps(result, indent=2))
        
        # Check for inline citations
        answer = result.get("answer", "")
        print("\n" + "="*50)
        print("ANSWER TEXT:")
        print("="*50)
        print(answer)
        
        if "[1]" in answer or "[2]" in answer:
            print("\n✅ SUCCESS: Inline citation markers found!")
        else:
            print("\n⚠️ WARNING: No inline citation markers found in answer")
            
except Exception as e:
    print(f"Error: {e}")
