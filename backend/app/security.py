from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from .config import get_settings

# PBKDF2 avoids native bcrypt version incompatibilities in simple local deployments.
# Use a centrally managed, reviewed password-hashing policy before production rollout.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ALGORITHM = "HS256"

def hash_password(password: str) -> str: return pwd_context.hash(password)
def verify_password(password: str, hashed: str) -> bool: return pwd_context.verify(password, hashed)
def create_token(parent_id: int) -> str:
    return jwt.encode({"sub": str(parent_id), "exp": datetime.now(timezone.utc) + timedelta(hours=12)}, get_settings().jwt_secret, algorithm=ALGORITHM)
def decode_token(token: str) -> int | None:
    try: return int(jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])["sub"])
    except (JWTError, KeyError, ValueError): return None
