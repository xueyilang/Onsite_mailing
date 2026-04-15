import os
import time
import json
from pathlib import Path
from typing import List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_PUBLIC_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"


def load_local_env(env_path: str = ".env") -> None:
    path = Path(env_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


load_local_env()


def get_env(name: str, default: str = "", required: bool = False) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        value = default
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value or ""


def split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def post_form(url: str, data: dict) -> dict:
    request = Request(
        url,
        data=urlencode(data).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(payload)
        except json.JSONDecodeError as json_exc:
            raise RuntimeError(f"HTTP {exc.code} calling {url}: {payload}") from json_exc
    except URLError as exc:
        raise RuntimeError(f"Network error calling {url}: {exc}") from exc


def post_json(url: str, payload: dict, headers: dict) -> tuple[int, str]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise RuntimeError(f"Network error calling {url}: {exc}") from exc


def get_json(url: str, headers: dict) -> tuple[int, str]:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise RuntimeError(f"Network error calling {url}: {exc}") from exc


def acquire_access_token() -> str:
    tenant_id = get_env("GRAPH_TENANT_ID", "common")
    client_id = get_env("GRAPH_CLIENT_ID", DEFAULT_PUBLIC_CLIENT_ID)
    scope = "https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/User.Read offline_access"
    base_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0"

    device_flow = post_form(
        f"{base_url}/devicecode",
        {"client_id": client_id, "scope": scope},
    )
    if "device_code" not in device_flow:
        raise RuntimeError(f"Failed to create device flow: {device_flow}")

    print(device_flow.get("message", "Open the verification URL and enter the code shown."))

    interval = int(device_flow.get("interval", 5))
    expires_in = int(device_flow.get("expires_in", 900))
    deadline = time.time() + expires_in

    while time.time() < deadline:
        time.sleep(interval)
        token_payload = post_form(
            f"{base_url}/token",
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": client_id,
                "device_code": device_flow["device_code"],
            },
        )
        if "access_token" in token_payload:
            return token_payload["access_token"]

        error = token_payload.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        raise RuntimeError(f"Device code login failed: {token_payload}")

    raise TimeoutError("Device code login timed out before authorization completed.")


def send_mail(access_token: str, to_addresses: List[str], subject: str, body: str) -> None:
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": item}} for item in to_addresses],
        },
        "saveToSentItems": True,
    }

    status_code, response_text = post_json(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        payload,
        {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    if status_code not in (200, 202):
        raise RuntimeError(f"Send mail failed: {status_code} {response_text}")


def show_signed_in_user(access_token: str) -> None:
    status_code, response_text = get_json(
        "https://graph.microsoft.com/v1.0/me",
        {"Authorization": f"Bearer {access_token}"},
    )
    if status_code != 200:
        raise RuntimeError(f"Get profile failed: {status_code} {response_text}")

    payload = json.loads(response_text)
    print(
        "Signed in as: "
        f"{payload.get('displayName', 'Unknown')} "
        f"<{payload.get('mail') or payload.get('userPrincipalName', 'unknown')}>"
    )


def main() -> None:
    to_addresses = split_csv(get_env("TEST_MAIL_TO", required=True))
    subject = get_env("TEST_MAIL_SUBJECT", "test")
    body = get_env("TEST_MAIL_BODY", "这是一封自动生成的邮件。")

    token = acquire_access_token()
    show_signed_in_user(token)
    send_mail(token, to_addresses, subject, body)

    print(f"Test mail sent to: {', '.join(to_addresses)}")


if __name__ == "__main__":
    main()
