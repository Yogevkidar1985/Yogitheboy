"""הרצה מקומית: python run.py  (או uvicorn app.main:app --reload)"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=os.environ.get("CLUB_HOST", "127.0.0.1"), port=int(os.environ.get("CLUB_PORT", "8000")), reload=os.environ.get("CLUB_RELOAD", "0") == "1")
