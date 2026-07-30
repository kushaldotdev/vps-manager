import os
from fastapi import FastAPI, Request, Response, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.auth import verify_password, create_session_token, verify_session_token
from app.executor import get_system_stats, get_services_status, stream_action, get_process_list

app = FastAPI(title="Oracle VPS Control Panel")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def check_auth(request: Request):
    token = request.cookies.get("vps_session")
    if not token or not verify_session_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/api/auth/login")
async def login(password: str = Form(...)):
    if verify_password(password):
        token = create_session_token()
        response = JSONResponse({"status": "success"})
        response.set_cookie(
            key="vps_session",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400
        )
        return response
    return JSONResponse({"status": "error", "message": "Invalid password"}, status_code=401)

@app.post("/api/auth/logout")
async def logout():
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie("vps_session")
    return response

@app.get("/api/auth/check")
async def check_session(request: Request):
    token = request.cookies.get("vps_session")
    if token and verify_session_token(token):
        return {"authenticated": True}
    return {"authenticated": False}

@app.get("/api/system", dependencies=[Depends(check_auth)])
async def api_system_stats():
    return get_system_stats()

@app.get("/api/processes", dependencies=[Depends(check_auth)])
async def api_processes():
    return get_process_list()

@app.get("/api/services", dependencies=[Depends(check_auth)])
async def api_services(request: Request):
    host_domain = request.headers.get("host", "")
    return get_services_status(host_domain=host_domain)

@app.post("/api/services/{service_id}/{action}", dependencies=[Depends(check_auth)])
async def api_service_action(service_id: str, action: str):
    return StreamingResponse(
        stream_action(service_id, action),
        media_type="text/plain"
    )

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r") as f:
        return HTMLResponse(content=f.read())
