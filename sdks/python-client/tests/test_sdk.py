import json
from dify_client import ChatClient

api_key = "app-hry33Idvg25gccpA2hDhMjfx"
base_url = "http://localhost:8000/v1"

# Initialize ChatClient
chat_client = ChatClient(api_key, base_url)

# Create Chat Message using ChatClient
chat_response = chat_client.create_chat_message(inputs={}, query="你好，做个自我介绍吧。", user="user_id", response_mode="streaming")
chat_response.raise_for_status()

print("\n")
for line in chat_response.iter_lines(decode_unicode=True):
    line = line.split('data:', 1)[-1]
    if line.strip():
        line = json.loads(line.strip())
        answer = line.get('answer')
        if(answer!=None):
            print(answer, end='', flush=True)
print("\n")