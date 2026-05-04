import os
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from typing import List, Optional

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
REALM = os.getenv("KEYCLOAK_REALM", "jobos")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "jobos-api")

# Keycloak JWKS URL for token validation
JWKS_URL = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs"

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
)

async def get_jwks():
    async with httpx.AsyncClient() as client:
        response = await client.get(JWKS_URL)
        return response.json()

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        jwks = await get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        
        if rsa_key:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                options={
                    "verify_aud": False,
                    "verify_at_hash": False,
                    "leeway": 30,  # 30s clock skew tolerance
                }
            )

            # Issuer must end with /realms/{REALM} — handles internal vs external URL mismatch
            iss = payload.get("iss", "")
            if not iss.endswith(f"/realms/{REALM}"):
                raise HTTPException(status_code=401, detail="Invalid issuer")

            return payload
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token header",
            )
    except HTTPException:
        raise  # never swallow HTTP exceptions into a 500
    except JWTError as e:
        print(f"JWT Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal auth error",
        )

def check_role(roles: List[str]):
    def role_verifier(payload: dict = Depends(get_current_user)):
        # Keycloak roles are usually in resource_access -> client_id -> roles
        # Or realm_access -> roles
        user_roles = payload.get("realm_access", {}).get("roles", [])
        
        # Also check client-specific roles if needed
        client_access = payload.get("resource_access", {}).get(CLIENT_ID, {})
        user_roles.extend(client_access.get("roles", []))
        
        if not any(role in user_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have enough permissions",
            )
        return payload
    return role_verifier
