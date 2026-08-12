from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

API_BASE = settings.SHIPROCKET_API_BASE or "https://apiv2.shiprocket.in/v1/external"

# ShipRocket v2 requires a JWT obtained from POST /auth/login (not the raw API
# key). The JWT is valid for 10 days, so we cache it and refresh on expiry or
# when a request bounces with 401.
_bearer_token: str | None = None
_token_expires_at: datetime | None = None


class ShipRocketNotConfigured(Exception):
    """Raised when ShipRocket integration is disabled or not fully configured."""


class ShipRocketError(Exception):
    """Raised when ShipRocket returns an error or the payload is rejected."""


class ShipRocketNotEnabledError(ShipRocketError):
    """Raised when the integration is disabled / not fully configured."""


def is_enabled() -> bool:
    """True when the integration is enabled AND has credentials + pickup location."""
    return bool(
        settings.SHIPROCKET_ENABLED
        and settings.SHIPROCKET_EMAIL
        and settings.SHIPROCKET_TOKEN
        and settings.SHIPROCKET_PICKUP_LOCATION
    )


def _login() -> str:
    """Exchange the API user credentials for a JWT via POST /auth/login."""
    url = (API_BASE.rstrip("/") + "/auth/login").strip("/")
    payload = {
        "email": settings.SHIPROCKET_EMAIL,
        "password": settings.SHIPROCKET_TOKEN,
    }
    try:
        resp = httpx.post(url, json=payload, timeout=30.0)
    except httpx.HTTPError as e:
        logger.warning("ShipRocket login network error: %s", e)
        raise ShipRocketError(f"ShipRocket login failed: {e}") from e

    if resp.status_code >= 400:
        body = resp.text[:2000]
        logger.warning("ShipRocket login -> %s: %s", resp.status_code, body)
        raise ShipRocketError(f"ShipRocket login failed ({resp.status_code}): {body}")

    token = resp.json().get("token")
    if not token:
        raise ShipRocketError("ShipRocket login response did not contain a token")
    return token


def _ensure_token() -> str:
    """Return a cached JWT, logging in again if it has expired or was rejected."""
    global _bearer_token, _token_expires_at
    now = datetime.now(timezone.utc)
    if _bearer_token and _token_expires_at and now < _token_expires_at:
        return _bearer_token
    _bearer_token = _login()
    # The ShipRocket JWT is valid for 10 days; refresh after 9 to be safe.
    _token_expires_at = now + timedelta(days=9)
    return _bearer_token


def _invalidate_token() -> None:
    global _bearer_token, _token_expires_at
    _bearer_token = None
    _token_expires_at = None


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_ensure_token()}",
        "Content-Type": "application/json",
    }


def _request(
    method: str, path: str, payload: dict[str, Any] | None = None, _retry: bool = True
) -> dict[str, Any]:
    url = (API_BASE.rstrip("/") + "/" + path.lstrip("/")).strip("/")
    try:
        resp = httpx.request(
            method, url, headers=_headers(), json=payload, timeout=30.0
        )
    except httpx.HTTPError as e:
        logger.warning("ShipRocket HTTP error on %s %s: %s", method, path, e)
        raise ShipRocketError(f"ShipRocket network error on {path}: {e}") from e

    # A 401 usually means the cached JWT expired mid-flight — log in once more.
    if resp.status_code == 401 and _retry:
        _invalidate_token()
        return _request(method, path, payload, _retry=False)

    if resp.status_code >= 400:
        body = resp.text[:2000]
        logger.warning(
            "ShipRocket %s %s -> %s: %s", method, path, resp.status_code, body
        )
        raise ShipRocketError(
            f"ShipRocket {path} failed ({resp.status_code}): {body}"
        )

    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _looks_like_pincode(v: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", v))


def _extract_phone(token: str) -> str:
    """Return a 10-digit Indian mobile from a token like '9876543210' or '+91 9876543210'."""
    digits = re.sub(r"\D", "", token)
    if len(digits) >= 10 and digits[-10:][0] in "6789":
        return digits[-10:]
    return ""


_ISO2_COUNTRY = re.compile(r"[A-Za-z]{2}")
_COUNTRY_CODES = {"IN", "US", "UK", "AE", "AU", "CA", "DE", "FR", "SG", "PK", "SA", "ZA", "MY"}
_COUNTRY_NAMES = {"india", "bharat", "usa", "united states", "uk", "united kingdom", "uae", "united arab emirates"}


def parse_shipping_address(line: str | None) -> dict[str, str]:
    """
    Convert the one-line shipping address the storefront stores into the
    structured billing fields ShipRocket expects.

    Both storefronts build the line as:
        fullName, phone, street, city, state, pincode, country
    joined with ", " and empty values dropped. The country is usually "IN" and
    the pincode may be glued onto the state ("West Bengal - 700001"). We parse
    from the right (country + pincode + state + city are stable) and treat the
    remaining leading tokens as name + phone + street. Returns a dict of
    billing_* fields the caller uppercases as needed.
    """
    if not line:
        return {
            "billing_name": "",
            "billing_address": "",
            "billing_city": "",
            "billing_state": "",
            "billing_pincode": "",
            "billing_country": "India",
            "billing_phone": "",
        }
    parts = [p.strip() for p in line.split(",") if p and p.strip()]
    country = "India"
    if parts:
        last = parts[-1]
        # The trailing token is a country when it is a known name or a
        # recognised 2-letter code ("IN", "US"). A bare 2-letter abbreviation
        # like a state code ("WB") is deliberately NOT treated as a country.
        if _ISO2_COUNTRY.fullmatch(last) and last.upper() in _COUNTRY_CODES or last.lower() in _COUNTRY_NAMES:
            country = parts.pop(-1)

    # Pincode is usually its own token, but can be glued onto the state
    # ("West Bengal - 700001") or the country token.
    pincode = ""
    if parts:
        m = re.search(r"(\d{6})", parts[-1])
        if m:
            pincode = m.group(1)
            parts[-1] = parts[-1][: m.start()].rstrip(" -")
            if not parts[-1].strip():
                parts.pop(-1)
    state = parts.pop(-1).strip() if parts else ""
    city = parts.pop(-1).strip() if parts else ""

    # Led tokens: [fullName, phone, street...]. Pull the name and any phone
    # from the start, leaving the remaining text as the street / address.
    name = ""
    phone = ""
    if parts:
        name = parts.pop(0)
        if parts:
            phoned = _extract_phone(parts[0])
            if phoned:
                phone = phoned
                parts.pop(0)
    address = ", ".join(parts)
    return {
        "billing_name": name,
        "billing_address": address,
        "billing_city": city,
        "billing_state": state,
        "billing_pincode": pincode,
        "billing_country": country or "India",
        "billing_phone": phone,
    }


def create_order(
    order,
    user,
    items: list[dict[str, Any]],
    payment_method: str,
) -> dict[str, Any]:
    if not is_enabled():
        raise ShipRocketNotEnabledError(
            "ShipRocket not configured (ENABLED, EMAIL, TOKEN or PICKUP_LOCATION missing)"
        )

    addr = parse_shipping_address(order.shipping_address)
    name = (
        addr["billing_name"]
        or (getattr(user, "full_name", None) or "Customer")
    )[:70]
    phone = (
        addr["billing_phone"]
        or (getattr(user, "phone", None) or "")
    )
    if not phone:
        m = re.search(r"(?<!\d)(\d{10})(?!\d)", addr["billing_address"])
        if m:
            phone = m.group(1)

    order_id_str = getattr(order, "order_number", None) or str(order.id)
    order_date = (
        order.created_at.date().isoformat()
        if getattr(order, "created_at", None)
        else date.today().isoformat()
    )

    payload: dict[str, Any] = {
        "order_id": order_id_str,
        "order_date": order_date,
        "pickup_location": settings.SHIPROCKET_PICKUP_LOCATION,
        "billing_customer_name": name,
        "billing_last_name": "",
        "billing_address": (addr["billing_address"] or "").upper(),
        "billing_city": (addr["billing_city"] or "").upper(),
        "billing_state": (addr["billing_state"] or "").upper(),
        "billing_pincode": addr["billing_pincode"],
        "billing_country": (addr["billing_country"] or "India").upper(),
        "billing_email": (getattr(user, "email", "") or "").lower(),
        "billing_phone": phone,
        "shipping_is_billing": True,
        "payment_method": (payment_method or "prepaid").upper(),
        "sub_total": float(getattr(order, "subtotal", 0) or 0),
        "length": settings.SHIPROCKET_DEFAULT_LENGTH,
        "breadth": settings.SHIPROCKET_DEFAULT_BREADTH,
        "height": settings.SHIPROCKET_DEFAULT_HEIGHT,
        "weight": settings.SHIPROCKET_DEFAULT_WEIGHT,
        "order_items": [
            {
                "name": it.get("product_name") or it.get("name") or "Item",
                "sku": str(it.get("variant_id") or it.get("product_id") or "")[:60],
                "units": it.get("quantity", 1),
                "selling_price": float(it.get("price", 0)),
                "discount": float(it.get("discount", 0)),
                "tax": float(it.get("gst_amount", 0)),
                "hsn": it.get("hsn") or "",
            }
            for it in items
        ],
    }
    if payload["payment_method"] not in ("COD", "PREPAID"):
        payload["payment_method"] = "PREPAID"

    logger.info(
        "ShipRocket create_order id=%s number=%s items=%d payment=%s",
        order.id, order_id_str, len(items), payload["payment_method"],
    )
    return _request("POST", "/orders/create/adhoc", payload)


def assign_awb(shiprocket_order_id: str, courier_id: str | None = None) -> dict[str, Any]:
    payload = {"shipment_id": shiprocket_order_id}
    if courier_id:
        payload["courier_id"] = courier_id
    return _request("POST", "/courier/assign/awb", payload)


def generate_pickup(shipment_id: str) -> dict[str, Any]:
    return _request("POST", "/courier/generate/pickup", {"shipment_id": shipment_id})


def track(awb_code: str) -> dict[str, Any]:
    return _request("GET", f"/courier/track/awb/{awb_code}")