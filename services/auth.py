import time
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request


def create_access_token(user):
    now = int(time.time())
    payload = {
        "sub": str(user["id"]),
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "iat": now,
        "exp": now + 60 * 60 * 8,
        "iss": "frametruth",
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token):
    return jwt.decode(
        token,
        current_app.config["SECRET_KEY"],
        algorithms=["HS256"],
        issuer="frametruth",
    )


def get_bearer_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.split(" ", 1)[1].strip()
    return None


def require_auth(allowed_roles=None):
    def decorator(route_handler):
        @wraps(route_handler)
        def wrapper(*args, **kwargs):
            token = get_bearer_token()
            if not token:
                return jsonify({
                    "request_id": getattr(g, "request_id", ""),
                    "status": "error",
                    "error": "Authentication token is required.",
                }), 401

            try:
                claims = decode_token(token)
            except jwt.PyJWTError:
                return jsonify({
                    "request_id": getattr(g, "request_id", ""),
                    "status": "error",
                    "error": "Authentication token is invalid or expired.",
                }), 401

            if allowed_roles and claims.get("role") not in allowed_roles:
                return jsonify({
                    "request_id": getattr(g, "request_id", ""),
                    "status": "error",
                    "error": "You do not have permission for this action.",
                }), 403

            g.auth_user = claims
            return route_handler(*args, **kwargs)

        return wrapper

    return decorator
