import httpx
import logging
from datetime import datetime, timezone

logger = logging.getLogger("osint-dashboard")


async def safe_request(
    url: str,
    method: str = "GET",
    headers: dict = None,
    json_data: dict = None,
    timeout: float = 15.0,
) -> dict:
    """Make an HTTP request with comprehensive error handling."""
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            if method.upper() == "GET":
                resp = await client.get(url, headers=headers)
            elif method.upper() == "POST":
                resp = await client.post(url, headers=headers, json=json_data)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}

            if resp.status_code == 200:
                try:
                    return {"success": True, "data": resp.json(), "status_code": 200}
                except Exception:
                    return {"success": True, "data": resp.text, "status_code": 200}
            else:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}",
                    "status_code": resp.status_code,
                }
    except httpx.TimeoutException:
        return {"success": False, "error": "Request timed out"}
    except httpx.ConnectError:
        return {"success": False, "error": "Connection failed"}
    except Exception as e:
        logger.warning(f"Request error for {url}: {e}")
        return {"success": False, "error": str(e)}


def format_timestamp() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def build_response(success: bool, data: dict = None, error: str = None) -> dict:
    """Build a standardized API response."""
    return {
        "success": success,
        "timestamp": format_timestamp(),
        "data": data or {},
        "error": error,
    }
