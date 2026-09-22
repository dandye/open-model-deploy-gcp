"""Lightweight HTTP server adapting Anthropic /v1/messages and /v1/models to Vertex AI Gemma endpoint."""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import subprocess
import time
import urllib.request
import urllib.error

ENDPOINT_ID = os.environ.get("GEMMA_ENDPOINT_ID", "7071975776727334912")
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "secops-demo-env")
REGION = os.environ.get("GCP_REGION", "us-central1")
PORT = int(os.environ.get("ADAPTER_PORT", "8001"))

def get_token():
    res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True)
    return res.stdout.strip()

def format_gemma_prompt(messages):
    prompt_parts = []
    system_prompt = ""
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if isinstance(content, list):
            texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            content = "\n".join(texts)
        if role == "system":
            system_prompt += f"{content}\n\n"
        elif role == "user":
            full_user = f"{system_prompt}{content}" if system_prompt else content
            system_prompt = ""
            prompt_parts.append(f"<start_of_turn>user\n{full_user}<end_of_turn>")
        elif role == "assistant":
            prompt_parts.append(f"<start_of_turn>model\n{content}<end_of_turn>")
    prompt_parts.append("<start_of_turn>model\n")
    return "\n".join(prompt_parts)

class GemmaAdapterHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = json.loads(body)
        
        messages = data.get("messages", [])
        max_tokens = data.get("max_tokens", 2048)
        temperature = data.get("temperature", 0.0)
        
        formatted_prompt = format_gemma_prompt(messages)
        token = get_token()
        
        url = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/endpoints/{ENDPOINT_ID}:rawPredict"
        payload = {
            "prompt": formatted_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            data=json.dumps(payload).encode("utf-8")
        )
        
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
            predictions = resp_data.get("predictions", [])
            output_text = predictions[0] if predictions else ""
            if "Output:\n" in output_text:
                output_text = output_text.split("Output:\n", 1)[1].strip()
            
            resp_payload = {
                "id": f"msg_gemma_{int(time.time())}",
                "type": "message",
                "role": "assistant",
                "model": "gemma-3-4b-it",
                "content": [{"type": "text", "text": output_text}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {
                    "input_tokens": int(len(formatted_prompt.split()) * 1.3),
                    "output_tokens": int(len(output_text.split()) * 1.3)
                }
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp_payload).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def do_GET(self):
        if "/models" in self.path:
            models_data = {
                "object": "list",
                "data": [
                    {
                        "id": "gemma-3-4b-it",
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "google",
                        "type": "model"
                    }
                ]
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(models_data).encode("utf-8"))
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Gemma Adapter Live")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), GemmaAdapterHandler)
    print(f"Serving Gemma Adapter on port {PORT}...")
    server.serve_forever()
