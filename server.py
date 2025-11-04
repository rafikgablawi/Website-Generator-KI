# server.py
# Anforderungen: fastapi, uvicorn, httpx, pydantic, python-dotenv
import os, re, time
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# ------------------ ENV laden ------------------
load_dotenv()
BASE_URL = os.getenv("OLLAMA_CLOUD_BASE", "https://ollama.com/v1")
API_KEY  = os.getenv("OLLAMA_API_KEY")

# ------------------ FastAPI-App ----------------
app = FastAPI(title="Ollama Cloud Proxy")

# CORS: für Netlify-Domain eng setzen, für Tests '*' lassen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # z.B. ["https://deinname.netlify.app"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ Statische Datei (index.html) ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "index.html")

# /static zeigt auf das Projektverzeichnis (optional für Assets)
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")

@app.get("/")
def serve_index():
    if os.path.exists(INDEX_FILE):
        return FileResponse(INDEX_FILE)
    return JSONResponse({"error": "index.html nicht gefunden"}, status_code=404)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/upstream")
async def upstream():
    """Kleiner Sanity-Check Richtung Ollama Cloud."""
    if not API_KEY:
        return {"ok": False, "err": "OLLAMA_API_KEY fehlt"}
    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model":"qwen3-coder:480b-cloud",
        "messages":[{"role":"user","content":"ping"}],
        "max_tokens": 8,
        "stream": False
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type":"application/json"}
    limits  = httpx.Limits(max_keepalive_connections=2, max_connections=4)
    timeout = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(http2=False, limits=limits, timeout=timeout) as client:
        r = await client.post(url, headers=headers, json=payload)
        return {"status": r.status_code, "headers": dict(r.headers), "body": r.text[:200]}

# ------------------ Modelle --------------------
class Req(BaseModel):
    prompt: str
    model: str | None = None
    max_tokens: int | None = 1500
    temperature: float | None = 0.4

# ------------------ Helpers -------------------
def _strip_code_fences(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"^\s*```[a-zA-Z0-9]*\s*", "", text.strip())
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()

async def call_cloud(payload: dict) -> dict:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="OLLAMA_API_KEY fehlt.")
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
    }
    limits  = httpx.Limits(max_keepalive_connections=2, max_connections=4)
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=30.0)

    retriable = {502, 503, 504, 408}
    backoff = 1.0
    async with httpx.AsyncClient(http2=False, limits=limits, timeout=timeout) as client:
        for attempt in range(4):
            try:
                r = await client.post(url, headers=headers, json=payload)
                if r.status_code in retriable and attempt < 3:
                    time.sleep(backoff); backoff *= 2; continue
                if r.status_code >= 400:
                    raise HTTPException(status_code=r.status_code, detail=f"{r.text}")
                return r.json()
            except httpx.RequestError as e:
                if attempt < 3:
                    time.sleep(backoff); backoff *= 2; continue
                raise HTTPException(status_code=502, detail=f"Netzwerkfehler: {e}") from e

# ------------------ API: /generate -------------
@app.post("/generate")
async def generate(req: Req):
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt fehlt")

    model = (req.model or "qwen3-coder:480b-cloud").strip()

    system = (
        "Du bist ein KI-Webdesigner. Antworte ausschließlich mit einem "
        "vollständigen, lauffähigen HTML-Dokument. Verwende eingebettetes CSS. "
        "Keine externen Skripte/Stylesheets/Fonts. Sprache: Deutsch."
    )
    user = (
        f"Erstelle eine One-Page-Website basierend auf:\n\n{req.prompt}\n\n"
        "- responsiv, gut lesbar\n- dezentes Design\n- keine externen Abhängigkeiten\n"
        "- gib NUR das vollständige HTML-Dokument zurück"
    )

    payload = {
        "model": model,
        "messages": [
            {"role":"system","content": system},
            {"role":"user","content": user},
        ],
        "temperature": req.temperature if req.temperature is not None else 0.4,
        "max_tokens": req.max_tokens if req.max_tokens is not None else 1500,
        "stream": False,
    }

    data = await call_cloud(payload)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    html = _strip_code_fences(content)

    if not html or "<html" not in html.lower():
        html = (
            "<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Website</title><style>body{font-family:Arial;padding:24px;max-width:900px;margin:0 auto}</style>"
            f"</head><body><h1>Entwurf</h1><pre>{content}</pre></body></html>"
        )

    # Optional ein paar Meta-Header zurückspiegeln, falls vorhanden
    meta = data.get("usage", {}) if isinstance(data.get("usage", {}), dict) else {}
    return {"html": html, "meta": meta}

# ------------------ Main (lokal/Render) -------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))  # Render setzt $PORT
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
