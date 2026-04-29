import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qs

logger = logging.getLogger(__name__)


def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    """
    Validate Telegram WebApp initData using HMAC-SHA256.
    Returns the parsed data dict (with 'user' as a dict) if valid, None otherwise.
    """
    if not init_data:
        return None

    try:
        parsed = parse_qs(init_data, keep_blank_values=True)
        data = {k: v[0] for k, v in parsed.items()}
    except Exception:
        return None

    received_hash = data.pop('hash', None)
    if not received_hash:
        return None

    # Sort by key and create data-check-string
    data_check_string = '\n'.join(
        f'{k}={v}' for k, v in sorted(data.items())
    )

    # HMAC-SHA256 of bot_token with key "WebAppData"
    secret_key = hmac.new(
        b'WebAppData', bot_token.encode(), hashlib.sha256
    ).digest()

    # HMAC-SHA256 of data-check-string with secret_key
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    # Parse user JSON
    user_str = data.get('user')
    if user_str:
        try:
            data['user'] = json.loads(user_str)
        except json.JSONDecodeError:
            return None

    return data


def get_user_id_from_init_data(validated_data: dict) -> int | None:
    """Extract user ID from validated initData."""
    user = validated_data.get('user')
    if isinstance(user, dict):
        uid = user.get('id')
        return int(uid) if uid is not None else None
    return None
