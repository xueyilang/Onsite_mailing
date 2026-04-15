import html
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import ctypes
from ctypes import wintypes
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_PUBLIC_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
try:
    GERMANY_TZ = ZoneInfo("Europe/Berlin")
except ZoneInfoNotFoundError:
    GERMANY_TZ = None

FIELD_ORDER: List[Tuple[str, str]] = [
    ("上门单号", "上门单号"),
    ("周数 KW", "周数 KW"),
    ("日期", "日期"),
    ("人员", "人员"),
    ("SN编号", "SN编号"),
    ("联系人(工单)", "联系人(工单)"),
    ("地址信息", "地址信息"),
    ("联系方式", "联系方式"),
    ("方向", "方向"),
    ("解决方案提案", "解决方案提案"),
    ("备注", "备注"),
    ("现场备注", "现场备注"),
    ("标准品名（被使用）", "标准品名（被使用）"),
    ("数量", "数量"),
    ("SN(被使用)", "SN(被使用)"),
    ("标准品名（被取回）", "标准品名（被取回）"),
    ("数量（被取回)", "数量（被取回)"),
    ("SN(被取回)", "SN(被取回)"),
    ("状态", "状态"),
]


def load_local_env(env_path: str = ".env") -> None:
    path = Path(env_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


load_local_env()


def get_env(name: str, default: str = "", required: bool = False) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        value = default
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value or ""


def post_form(url: str, data: Dict[str, str]) -> Dict[str, Any]:
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


def post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            response_text = response.read().decode("utf-8", errors="replace").strip()
            return json.loads(response_text) if response_text else {}
    except HTTPError as exc:
        payload_text = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(payload_text)
        except json.JSONDecodeError as json_exc:
            raise RuntimeError(f"HTTP {exc.code} calling {url}: {payload_text}") from json_exc
    except URLError as exc:
        raise RuntimeError(f"Network error calling {url}: {exc}") from exc


def get_json(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload_text = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(payload_text)
        except json.JSONDecodeError as json_exc:
            raise RuntimeError(f"HTTP {exc.code} calling {url}: {payload_text}") from json_exc
    except URLError as exc:
        raise RuntimeError(f"Network error calling {url}: {exc}") from exc


def normalize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(part for part in (normalize_value(item) for item in value) if part)
    if isinstance(value, dict):
        if "text" in value:
            return normalize_value(value["text"])
        if "name" in value:
            return normalize_value(value["name"])
        if "email" in value:
            return normalize_value(value["email"])
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def format_field_value(field_name: str, value: Any) -> str:
    normalized = normalize_value(value)
    if field_name in ("上门单号", "状态"):
        return normalized.replace("\r", " ").replace("\n", " ")
    if field_name == "日期":
        if isinstance(value, (int, float)):
            return format_germany_datetime(float(value))
        if isinstance(value, str) and value.isdigit():
            return format_germany_datetime(float(value))
        return normalized
    return normalized


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
    ]


def format_germany_datetime(timestamp_ms: float) -> str:
    dt_utc = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    if GERMANY_TZ is not None:
        return dt_utc.astimezone(GERMANY_TZ).strftime("%d.%m.%Y %H:%M")
    return format_windows_germany_time(dt_utc)


def format_windows_germany_time(dt_utc: datetime) -> str:
    system_time = SYSTEMTIME(
        wYear=dt_utc.year,
        wMonth=dt_utc.month,
        wDay=dt_utc.day,
        wHour=dt_utc.hour,
        wMinute=dt_utc.minute,
        wSecond=dt_utc.second,
        wMilliseconds=int(dt_utc.microsecond / 1000),
        wDayOfWeek=dt_utc.weekday(),
    )
    local_time = SYSTEMTIME()
    result = ctypes.windll.kernel32.SystemTimeToTzSpecificLocalTimeEx(
        None,
        ctypes.byref(system_time),
        ctypes.byref(local_time),
    )
    if result == 0:
        return dt_utc.strftime("%d.%m.%Y %H:%M")
    return (
        f"{local_time.wDay:02d}.{local_time.wMonth:02d}.{local_time.wYear:04d} "
        f"{local_time.wHour:02d}:{local_time.wMinute:02d}"
    )


def acquire_feishu_token() -> str:
    app_id = get_env("FEISHU_APP_ID", required=True)
    app_secret = get_env("FEISHU_APP_SECRET", required=True)
    base_url = get_env("FEISHU_BASE_URL", "https://open.feishu.cn")

    payload = post_json(
        f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
        {"Content-Type": "application/json"},
    )
    if payload.get("code") != 0:
        raise RuntimeError(f"Feishu auth failed: {payload}")
    return payload["tenant_access_token"]


def list_feishu_records() -> List[Dict[str, Any]]:
    base_url = get_env("FEISHU_BASE_URL", "https://open.feishu.cn")
    app_token = get_env("FEISHU_APP_TOKEN", required=True)
    table_id = get_env("FEISHU_TABLE_ID", required=True)
    view_id = get_env("FEISHU_VIEW_ID")
    page_size = get_env("FEISHU_PAGE_SIZE", "100")
    token = acquire_feishu_token()

    page_token = ""
    records: List[Dict[str, Any]] = []
    while True:
        params = [f"page_size={page_size}"]
        if page_token:
            params.append(f"page_token={page_token}")
        if view_id:
            params.append(f"view_id={view_id}")
        query = "&".join(params)
        url = f"{base_url}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records?{query}"
        payload = get_json(url, {"Authorization": f"Bearer {token}"})
        if payload.get("code") != 0:
            raise RuntimeError(f"Feishu record query failed: {payload}")

        data = payload.get("data", {})
        for item in data.get("items", []):
            records.append(item.get("fields", {}))

        if not data.get("has_more"):
            return records
        page_token = data.get("page_token", "")


def record_matches(record: Dict[str, Any]) -> bool:
    week_value = normalize_value(record.get("周数 KW")).strip()
    direction_value = normalize_value(record.get("方向")).strip()
    person_value = normalize_value(record.get("人员")).strip()
    return week_value == "KW12" and direction_value == "Berlin" and person_value != ""


def project_record(record: Dict[str, Any]) -> Dict[str, str]:
    return {label: format_field_value(field_name, record.get(field_name)) for field_name, label in FIELD_ORDER}


def collect_people(records: List[Dict[str, Any]]) -> str:
    people: List[str] = []
    for record in records:
        person = format_field_value("人员", record.get("人员")).strip()
        if person and person not in people:
            people.append(person)
    return ", ".join(people)


def summarize_filter_inputs(records: List[Dict[str, Any]]) -> str:
    def collect(field_name: str) -> List[str]:
        values = []
        for record in records:
            value = normalize_value(record.get(field_name)).strip()
            if value and value not in values:
                values.append(value)
            if len(values) >= 10:
                break
        return values

    weeks = collect("周数 KW")
    directions = collect("方向")
    people = collect("人员")
    return (
        f"Sample 周数 KW: {weeks}\n"
        f"Sample 方向: {directions}\n"
        f"Sample 人员: {people}"
    )


def build_html_table(rows: List[Dict[str, str]]) -> str:
    headers = [label for _, label in FIELD_ORDER]
    nowrap_columns = {"上门单号", "日期", "状态", "周数 KW"}
    wide_columns = {"解决方案提案", "现场备注"}
    medium_columns = {"上门单号", "日期"}
    narrow_columns = {"标准品名（被使用）", "标准品名（被取回）"}
    header_html = "".join(
        (
            f"<th style='border:1px solid #cfcfcf;padding:8px;background:#f5f5f5;text-align:left;"
            f"{'white-space:nowrap;word-break:keep-all;' if label in nowrap_columns else ''}"
            f"{'min-width:230px;white-space:normal;' if label in wide_columns else ''}"
            f"{'min-width:100px;' if label in medium_columns else ''}"
            f"{'min-width:45px;' if label in narrow_columns else ''}'>"
            f"{html.escape(label)}</th>"
        )
        for label in headers
    )
    body_rows = []
    for row in rows:
        cells = "".join(
            (
                f"<td style='border:1px solid #cfcfcf;padding:8px;vertical-align:top;"
                f"{'min-width:230px;white-space:normal;' if label in wide_columns else ''}"
                f"{'white-space:nowrap;word-break:keep-all;' if label in nowrap_columns else ''}"
                f"{'min-width:100px;' if label in medium_columns else ''}"
                f"{'min-width:45px;' if label in narrow_columns else ''}'>"
                f"{html.escape(row.get(label, ''))}</td>"
            )
            for label in headers
        )
        body_rows.append(f"<tr>{cells}</tr>")

    if not body_rows:
        empty_cell = (
            f"<td colspan='{len(headers)}' style='border:1px solid #cfcfcf;padding:8px;'>"
            "No records matched the filter."
            "</td>"
        )
        body_rows.append(f"<tr>{empty_cell}</tr>")

    return (
        "<table style='border-collapse:collapse;font-family:Segoe UI,Arial,sans-serif;font-size:12px;table-layout:auto;'>"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def acquire_graph_token() -> str:
    tenant_id = get_env("GRAPH_TENANT_ID", required=True)
    client_id = get_env("GRAPH_CLIENT_ID", DEFAULT_PUBLIC_CLIENT_ID)
    scope = "https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/User.Read offline_access"
    base_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0"

    device_flow = post_form(f"{base_url}/devicecode", {"client_id": client_id, "scope": scope})
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


def send_mail(access_token: str, subject: str, html_body: str) -> None:
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": "marco.xue@alpha-ess.de"}}],
            "ccRecipients": [],
        },
        "saveToSentItems": True,
    }

    response = post_json(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        payload,
        {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    if response:
        error = response.get("error")
        if error:
            raise RuntimeError(f"Send mail failed: {response}")


def main() -> None:
    subject = "2026 KW12欧洲技术外勤及售后备品使用情况 KW12 Onsite Service"
    records = list_feishu_records()
    matched_records = [record for record in records if record_matches(record)]
    people_text = collect_people(matched_records) or "N/A"
    filtered_rows = [project_record(record) for record in matched_records]
    print(f"Total records fetched: {len(records)}")
    print(f"Matched records: {len(filtered_rows)}")
    if not filtered_rows:
        print(summarize_filter_inputs(records))

    intro = (
        "<p style='font-family:Segoe UI,Arial,sans-serif;font-size:12px;'>"
        "Dear All,<br><br>"
        f"下表是2026 KW09欧洲技术外勤及售后备品使用情况，由 {html.escape(people_text)} 执行：<br>"
        f"the onsite Service in 2026 KW09 was carried out by {html.escape(people_text)}, the details are following:"
        "</p>"
    )
    summary = (
        "<p style='font-family:Segoe UI,Arial,sans-serif;font-size:12px;'>"
        f"Matched records: {len(filtered_rows)}"
        "</p>"
    )
    html_body = intro + summary + build_html_table(filtered_rows)

    access_token = acquire_graph_token()
    send_mail(access_token, subject, html_body)
    print("Mail sent to marco.xue@alpha-ess.de")


if __name__ == "__main__":
    main()
