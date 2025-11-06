# server.py
import os, re, time
from pathlib import Path
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- Konfiguration ---
OLLAMA_API_KEY     = os.getenv("OLLAMA_API_KEY", "").strip()
OLLAMA_CLOUD_BASE  = os.getenv("OLLAMA_CLOUD_BASE", "https://ollama.com/v1").rstrip("/")

BASE_DIR   = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

# --- FastAPI ---
app = FastAPI(title="Website-Generator KI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Render + lokal problemlos
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Statische Dateien unter /static bereitstellen
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- Routen ---
@app.get("/")
def root():
    if INDEX_FILE.exists():
        return FileResponse(str(INDEX_FILE), media_type="text/html; charset=utf-8")
    return JSONResponse({"error": "index.html fehlt"}, status_code=404)

# Alias, damit /logo.jpg direkt funktioniert (Render-Logs zeigten 404 darauf)
@app.get("/logo.jpg")
def logo_alias():
    path = STATIC_DIR / "logo.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="logo.jpg fehlt unter static/")
    return FileResponse(str(path), media_type="image/jpeg")

@app.get("/health")
def health():
    return {"ok": True, "api_key_set": bool(OLLAMA_API_KEY), "base": OLLAMA_CLOUD_BASE}

# --- Datamodel ---
class Req(BaseModel):
    prompt: str
    model: str | None = "qwen3-coder:480b-cloud"
    max_tokens: int | None = 1000
    temperature: float | None = 0.4

# --- Helper ---
def _strip_fences(txt: str) -> str:
    if not txt:
        return txt
    txt = re.sub(r"^\s*```[a-zA-Z0-9]*\s*", "", txt.strip())
    txt = re.sub(r"\s*```\s*$", "", txt)
    return txt.strip()

async def _call_ollama(payload: dict) -> dict:
    if not OLLAMA_API_KEY:
        raise HTTPException(status_code=500, detail="OLLAMA_API_KEY fehlt")
    url = f"{OLLAMA_CLOUD_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OLLAMA_API_KEY}",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
    }
    limits  = httpx.Limits(max_keepalive_connections=2, max_connections=4)
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=20.0, pool=20.0)
    retriable = {408, 502, 503, 504}

    async with httpx.AsyncClient(http2=False, limits=limits, timeout=timeout) as client:
        backoff = 1.0
        for attempt in range(2):
            try:
                r = await client.post(url, headers=headers, json=payload)
                if r.status_code in retriable and attempt == 0:
                    time.sleep(backoff); backoff *= 2; continue
                if r.status_code >= 400:
                    raise HTTPException(status_code=502, detail=f"Provider {r.status_code}: {r.text[:400]}")
                return r.json()
            except httpx.RequestError as e:
                if attempt == 0:
                    time.sleep(1.5); continue
                raise HTTPException(status_code=502, detail=f"Netzwerkfehler: {e}")

# --- API ---
@app.post("/generate")
async def generate(req: Req):
    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt fehlt")

    model       = (req.model or "qwen3-coder:480b-cloud").strip()
    max_tokens  = int(req.max_tokens or 1000)
    temperature = float(req.temperature if req.temperature is not None else 0.4)

    system = (
        "Du bist ein KI-Webdesigner. Antworte ausschließlich mit einem vollständigen, "
        "lauffähigen HTML-Dokument mit eingebettetem CSS. Keine externen Skripte/Fonts."
    )
    user = (
        f"Erstelle eine moderne One-Page-Website basierend auf:\n\n{prompt}\n\n"
        "- responsiv, gut lesbar\n- dezentes Design\n- keine externen Abhängigkeiten\n"
        "- gib NUR das vollständige HTML-Dokument zurück"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    data = await _call_ollama(payload)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    html = _strip_fences(content)

    if "<html" not in html.lower():
        html = (
            "<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Entwurf</title><style>body{font-family:Arial;padding:24px;max-width:900px;margin:0 auto}</style>"
            f"</head><body><h1>Entwurf</h1><pre>{content}</pre></body></html>"
        )

    usage = data.get("usage", {}) if isinstance(data.get("usage", {}), dict) else {}
    return {"html": html, "meta": usage}

# --- Start (Render setzt $PORT) ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
