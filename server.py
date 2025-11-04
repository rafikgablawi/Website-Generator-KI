import os, re, time, httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("OLLAMA_CLOUD_BASE", "https://ollama.com/v1")
API_KEY  = os.getenv("OLLAMA_API_KEY")

app = FastAPI(title="Ollama Cloud Proxy")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"ok": True, "msg": "Ollama Cloud Proxy läuft", "endpoints": ["/health", "/generate"]}

@app.get("/health")
def health():
    return {"ok": True}

class Req(BaseModel):
    prompt: str
    model: str | None = None

def _strip_code_fences(t:str)->str:
    if not t: return t
    import re
    t = re.sub(r"^\s*```[a-zA-Z0-9]*\s*", "", t.strip())
    t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()

async def call_cloud(payload: dict) -> dict:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="OLLAMA_API_KEY fehlt.")
    url = f"{BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json", "Connection":"keep-alive"}

    limits = httpx.Limits(max_keepalive_connections=2, max_connections=4)
    timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=30.0)

    retriable = {502,503,504,408}
    backoff = 1.0
    async with httpx.AsyncClient(http2=False, limits=limits, timeout=timeout) as client:
        for attempt in range(4):
            try:
                r = await client.post(url, headers=headers, json=payload)
                if r.status_code in retriable and attempt < 3:
                    time.sleep(backoff); backoff *= 2; continue
                if r.status_code >= 400:
                    raise HTTPException(status_code=r.status_code, detail=r.text)
                return r.json()
            except httpx.RequestError as e:
                if attempt < 3:
                    time.sleep(backoff); backoff *= 2; continue
                raise HTTPException(status_code=502, detail=f"Netzwerkfehler: {e}") from e

@app.post("/generate")
async def generate(req: Req):
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt fehlt")
    model = (req.model or "qwen3-coder:480b-cloud").strip()

    system = ("Du bist ein KI-Webdesigner. Antworte ausschließlich mit einem vollständigen HTML-Dokument. "
              "Eingebettetes CSS. Keine externen Skripte.")
    user = (f"Erstelle eine One-Page-Website basierend auf:\n\n{req.prompt}\n\n"
            "- responsiv, gute Lesbarkeit\n- keine externen Abhängigkeiten\n- gib NUR das HTML-Dokument zurück")

    payload = {"model": model,
               "messages": [{"role":"system","content":system},{"role":"user","content":user}],
               "temperature": 0.4, "max_tokens": 1500, "stream": False}

    data = await call_cloud(payload)
    content = data.get("choices",[{}])[0].get("message",{}).get("content","")
    html = _strip_code_fences(content)
    if not html or "<html" not in html.lower():
        html = ("<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>Website</title><style>body{font-family:Arial;padding:24px;max-width:900px;margin:0 auto}</style>"
                f"</head><body><h1>Entwurf</h1><pre>{content}</pre></body></html>")
    return {"html": html}

# Start: uvicorn server:app --host 127.0.0.1 --port 8000 --reload
