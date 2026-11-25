"""Lanzador local para NetPulse La Paz (PWA + API + IA)."""

import uvicorn

if __name__ == "__main__":
    print("Iniciando NetPulse La Paz en http://127.0.0.1:8000 ...")
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)
