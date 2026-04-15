"""
初中数学错题分析 - FastAPI 服务
"""

import base64, json, re, os
import api_client, storage
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="数学错题分析")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

HTML_TEMPLATE = open("templates/index.html").read()


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_TEMPLATE


@app.get("/health")
async def health():
    return {"status": "ok", "db_path": os.environ.get("RENDER_DISK_PATH", "/tmp")}


@app.post("/api/analyze")
async def analyze(image: UploadFile = File(...), extra: str = Form("")):
    img_bytes = await image.read()
    img_b64 = base64.b64encode(img_bytes).decode()
    try:
        raw = api_client.analyze_image(img_b64, extra)
        record_id = storage.save_record(raw, img_b64)
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        result = json.loads(match.group()) if match else {"raw": raw}
        result["record_id"] = record_id
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/records")
async def get_records():
    records = storage.get_records(50)
    for r in records:
        r.pop("image_b64", None)
        r.pop("raw_result", None)
    return records


@app.get("/api/stats")
async def get_stats():
    return storage.get_stats()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
