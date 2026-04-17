import requests
import json

# Test the health endpoint
response = requests.get("http://localhost:8000/api/v1/health")
print("Health check:", response.json())

# Test asking a question
question_data = {
    "question": "saya sudahjh aktivasi akun emasjid?",
    "model": "openai/gpt-3.5-turbo"
}

response = requests.post("http://localhost:8000/api/v1/ask", json=question_data)
print("Question response:", response.json())

# Test uploading a document (you'll need to have a test.pdf file)
# files = {"file": open("test.pdf", "rb")}
# response = requests.post("http://localhost:8000/api/v1/upload-document", files=files)
# print("Upload response:", response.json())