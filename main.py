import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from pathlib import Path
import os
import secrets

from star_maps import generate_star_map_image, generate_star_map_gif, generate_star_map_video

# =====================================================
# CONFIGURATION
# =====================================================
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

fake_users_db = {
    "alice": {"username": "alice", "password": "password123", "role": "user"},
    "admin": {"username": "admin", "password": "adminpass", "role": "admin"},
}

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# =====================================================
# AUTHENTICATION
# =====================================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def authenticate_user(username: str, password: str):
    user = fake_users_db.get(username)
    if not user or user["password"] != password:
        return None
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = fake_users_db.get(username)
    if not user:
        raise credentials_exception
    return user

# =====================================================
# APP INITIALISATION
# =====================================================
app = FastAPI(title="Stellify API", version="1.0.0")

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    access_token = create_access_token(data={"sub": user["username"]},
                                       expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer"}

# =====================================================
# ENDPOINTS
# =====================================================
@app.post("/png")
async def generate_png(location: str, when: str, chart_size: int = 12, max_star_size: int = 100,
                       current_user: dict = Depends(get_current_user)):
    generate_star_map_image(location, when, chart_size, max_star_size)
    return {"status": "PNG generated", "file_path": str(OUTPUT_DIR)}

@app.post("/gif")
async def generate_gif(location: str, when: str, hours: int = 1, step_minutes: int = 30,
                       chart_size: int = 12, max_star_size: int = 100,
                       current_user: dict = Depends(get_current_user)):
    generate_star_map_gif(location, when, hours, step_minutes, chart_size, max_star_size)
    return {"status": "GIF generated", "file_path": str(OUTPUT_DIR)}

@app.post("/video")
async def generate_video(location: str, when: str, hours: int = 1, step_minutes: int = 30,
                         chart_size: int = 12, max_star_size: int = 100, fps: int = 30,
                         current_user: dict = Depends(get_current_user)):
    generate_star_map_video(location, when, hours, step_minutes, chart_size, max_star_size, fps=fps)
    return {"status": "Video generated", "file_path": str(OUTPUT_DIR)}

# =====================================================
# RUN LOCALLY
# =====================================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
