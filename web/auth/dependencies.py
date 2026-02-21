import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from web.config.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer()

def get_current_client_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Validate JWT token and return the client_id."""
    token = credentials.credentials
    secret_key = os.getenv("JWT_SECRET_KEY")
    allowed_clients_str = os.getenv("ALLOWED_CLIENT_IDS", "")
    allowed_clients = [c.strip() for c in allowed_clients_str.split(",") if c.strip()]
    
    if not secret_key:
        logger.error("JWT_SECRET_KEY is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured properly"
        )
        
    try:
        # Payload usually has sub = client_id
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        client_id = payload.get("sub")
        if not client_id:
            logger.warning("Token missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token"
            )
            
        if allowed_clients and client_id not in allowed_clients:
            logger.warning(f"Client {client_id} not in allowed list")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Client not authorized"
            )
            
        return client_id
        
    except jwt.ExpiredSignatureError:
        logger.warning("Expired token used")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token used: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token"
        )
