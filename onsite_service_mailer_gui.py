import ctypes
import base64
import html
import json
import os
import sys
import time
import webbrowser
import threading
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_PUBLIC_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
EMBEDDED_DEFAULTS = {
    "FEISHU_APP_ID": "cli_a90f497cbd38dcc4",
    "FEISHU_APP_SECRET": "qohFgu8mnXnRH484mRYsEbxc32hcxu4y",
    "FEISHU_BASE_URL": "https://open.feishu.cn",
    "FEISHU_APP_TOKEN": "G2GHbHVWRarPAPstB0hjPliRpvf",
    "FEISHU_TABLE_ID": "tblHCxh8GzFQMxtO",
    "FEISHU_VIEW_ID": "",
    "FEISHU_PAGE_SIZE": "100",
    "GRAPH_TENANT_ID": "683d9da1-dec0-4323-b112-b5b69607660c",
    "GRAPH_CLIENT_ID": "184c84fe-ec2d-4ad6-aef6-e50b3a06b742",
}
try:
    GERMANY_TZ = ZoneInfo("Europe/Berlin")
except ZoneInfoNotFoundError:
    GERMANY_TZ = None

BASE_FIELDS: List[Tuple[str, str]] = [
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
    ("状态", "状态"),
]

ONSITE_EXTRA_FIELDS: List[Tuple[str, str]] = [
    ("现场备注", "现场备注"),
    ("标准品名（被使用）", "标准品名（被使用）"),
    ("数量", "数量"),
    ("SN(被使用)", "SN(被使用)"),
    ("标准品名（被取回）", "标准品名（被取回）"),
    ("数量（被取回)", "数量（被取回)"),
    ("SN(被取回)", "SN(被取回)"),
]

DEFAULT_DIRECTIONS = [
    "Berlin",
    "München",
    "NRW",
    "One Day",
    "Dresden",
    "Stuttgurt",
    "Würzburg",
    "Hamburg",
    "Bremen",
    "Nürnberg",
    "Trier",
    "Oldenburg",
    "Leipzig",
    "NRW+Hannover",
    "Österreich",
    "Switzerland",
]


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


def load_local_env(env_path: str = ".env") -> None:
    path = Path(env_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line or line.startswith(";"):
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


load_local_env()


def configure_tcl_tk() -> None:
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        tcl_dir = base_dir / "tcl" / "tcl8.6"
        tk_dir = base_dir / "tcl" / "tk8.6"
        if tcl_dir.exists():
            os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
        if tk_dir.exists():
            os.environ.setdefault("TK_LIBRARY", str(tk_dir))
    else:
        py_base = Path(sys.base_prefix)
        tcl_dir = py_base / "tcl" / "tcl8.6"
        tk_dir = py_base / "tcl" / "tk8.6"
        if tcl_dir.exists():
            os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
        if tk_dir.exists():
            os.environ.setdefault("TK_LIBRARY", str(tk_dir))


configure_tcl_tk()

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def get_env(name: str, default: str = "", required: bool = False) -> str:
    embedded_default = EMBEDDED_DEFAULTS.get(name, default)
    value = os.getenv(name, embedded_default)
    if value is None or value == "":
        value = embedded_default
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
            text = response.read().decode("utf-8", errors="replace").strip()
            return json.loads(text) if text else {}
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


def germany_datetime_from_ms(timestamp_ms: float) -> datetime:
    dt_utc = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    if GERMANY_TZ is not None:
        return dt_utc.astimezone(GERMANY_TZ)
    return dt_utc.astimezone()


def format_germany_datetime(timestamp_ms: float) -> str:
    dt_utc = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    if GERMANY_TZ is not None:
        return dt_utc.astimezone(GERMANY_TZ).strftime("%d.%m.%Y %H:%M")
    return format_windows_germany_time(dt_utc)


def format_field_value(field_name: str, value: Any) -> str:
    normalized = normalize_value(value)
    if field_name in {"上门单号", "状态"}:
        return normalized.replace("\r", " ").replace("\n", " ")
    if field_name == "日期":
        if isinstance(value, (int, float)):
            return format_germany_datetime(float(value))
        if isinstance(value, str) and value.isdigit():
            return format_germany_datetime(float(value))
    return normalized


class FeishuClient:
    def __init__(self) -> None:
        self.base_url = get_env("FEISHU_BASE_URL", "https://open.feishu.cn")
        self.app_id = get_env("FEISHU_APP_ID", required=True)
        self.app_secret = get_env("FEISHU_APP_SECRET", required=True)
        self.app_token = get_env("FEISHU_APP_TOKEN", required=True)
        self.table_id = get_env("FEISHU_TABLE_ID", required=True)
        self.view_id = get_env("FEISHU_VIEW_ID")
        self.page_size = get_env("FEISHU_PAGE_SIZE", "100")

    def acquire_token(self) -> str:
        payload = post_json(
            f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal",
            {"app_id": self.app_id, "app_secret": self.app_secret},
            {"Content-Type": "application/json"},
        )
        if payload.get("code") != 0:
            raise RuntimeError(f"Feishu auth failed: {payload}")
        return payload["tenant_access_token"]

    def list_records(self) -> List[Dict[str, Any]]:
        token = self.acquire_token()
        page_token = ""
        records: List[Dict[str, Any]] = []
        while True:
            params = [f"page_size={self.page_size}"]
            if page_token:
                params.append(f"page_token={page_token}")
            if self.view_id:
                params.append(f"view_id={self.view_id}")
            url = (
                f"{self.base_url}/open-apis/bitable/v1/apps/{self.app_token}/tables/"
                f"{self.table_id}/records?{'&'.join(params)}"
            )
            payload = get_json(url, {"Authorization": f"Bearer {token}"})
            if payload.get("code") != 0:
                raise RuntimeError(f"Feishu record query failed: {payload}")

            data = payload.get("data", {})
            for item in data.get("items", []):
                records.append(item.get("fields", {}))
            if not data.get("has_more"):
                return records
            page_token = data.get("page_token", "")


class GraphMailer:
    def __init__(self) -> None:
        self.tenant_id = get_env("GRAPH_TENANT_ID", required=True)
        self.client_id = get_env("GRAPH_CLIENT_ID", DEFAULT_PUBLIC_CLIENT_ID)
        self.scope = "https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/User.Read offline_access"

    def acquire_token(self, status_callback, device_code_callback) -> str:
        base_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0"
        device_flow = post_form(
            f"{base_url}/devicecode",
            {"client_id": self.client_id, "scope": self.scope},
        )
        if "device_code" not in device_flow:
            raise RuntimeError(f"Failed to create device flow: {device_flow}")

        verification_uri = device_flow.get("verification_uri") or "https://login.microsoft.com/device"
        user_code = device_flow.get("user_code", "")
        status_callback(
            "请在浏览器中完成登录。\n"
            f"打开: {verification_uri}\n"
            f"输入代码: {user_code}"
        )
        device_code_callback(user_code, verification_uri)

        interval = int(device_flow.get("interval", 5))
        deadline = time.time() + int(device_flow.get("expires_in", 900))
        while time.time() < deadline:
            time.sleep(interval)
            token_payload = post_form(
                f"{base_url}/token",
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": self.client_id,
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

    def send_mail(
        self,
        access_token: str,
        subject: str,
        html_body: str,
        to_addresses: List[str],
        cc_addresses: List[str],
        attachment_paths: List[str],
    ) -> None:
        attachments = []
        for attachment_path in attachment_paths:
            path = Path(attachment_path)
            content_bytes = base64.b64encode(path.read_bytes()).decode("utf-8")
            attachments.append(
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": path.name,
                    "contentType": "application/pdf" if path.suffix.lower() == ".pdf" else "application/octet-stream",
                    "contentBytes": content_bytes,
                }
            )
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_body},
                "toRecipients": [{"emailAddress": {"address": item}} for item in to_addresses],
                "ccRecipients": [{"emailAddress": {"address": item}} for item in cc_addresses],
                "attachments": attachments,
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
        if response.get("error"):
            raise RuntimeError(f"Send mail failed: {response}")

    def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        response = get_json(
            "https://graph.microsoft.com/v1.0/me",
            {"Authorization": f"Bearer {access_token}"},
        )
        if response.get("error"):
            raise RuntimeError(f"Get profile failed: {response}")
        return response


def collect_people(records: List[Dict[str, Any]]) -> str:
    people: List[str] = []
    for record in records:
        raw_person = format_field_value("人员", record.get("人员")).strip()
        if not raw_person:
            continue
        for person in [part.strip() for part in raw_person.replace("，", ",").split(",") if part.strip()]:
            if person not in people:
                people.append(person)
    return ", ".join(people)


def infer_year(records: List[Dict[str, Any]]) -> int:
    for record in records:
        raw_value = record.get("日期")
        if isinstance(raw_value, (int, float)):
            return germany_datetime_from_ms(float(raw_value)).year
        if isinstance(raw_value, str) and raw_value.isdigit():
            return germany_datetime_from_ms(float(raw_value)).year
    now = datetime.now(GERMANY_TZ) if GERMANY_TZ is not None else datetime.now()
    return now.year


def record_matches(record: Dict[str, Any], kw: str, direction: str) -> bool:
    week_value = normalize_value(record.get("周数 KW")).strip()
    direction_value = normalize_value(record.get("方向")).strip()
    person_value = normalize_value(record.get("人员")).strip()
    return (
        week_value.lower() == kw.strip().lower()
        and direction_value.lower() == direction.strip().lower()
        and person_value != ""
    )


def project_record(record: Dict[str, Any], include_onsite_details: bool) -> Dict[str, str]:
    field_order = BASE_FIELDS + (ONSITE_EXTRA_FIELDS if include_onsite_details else [])
    return {label: format_field_value(field_name, record.get(field_name)) for field_name, label in field_order}


def build_html_table(rows: List[Dict[str, str]], include_onsite_details: bool) -> str:
    field_order = BASE_FIELDS + (ONSITE_EXTRA_FIELDS if include_onsite_details else [])
    headers = [label for _, label in field_order]
    nowrap_columns = {"上门单号", "日期", "状态", "周数 KW"}
    wide_columns = {"解决方案提案", "现场备注"}
    medium_columns = {"上门单号", "日期"}
    narrow_columns = {"标准品名（被使用）", "标准品名（被取回）"}
    person_columns = {"人员"}

    header_html = "".join(
        (
            f"<th style='border:1px solid #cfcfcf;padding:8px;background:#f5f5f5;text-align:left;"
            f"{'white-space:nowrap;word-break:keep-all;' if label in nowrap_columns else ''}"
            f"{'min-width:230px;white-space:normal;' if label in wide_columns else ''}"
            f"{'min-width:100px;' if label in medium_columns else ''}"
            f"{'min-width:45px;' if label in narrow_columns else ''}"
            f"{'min-width:50px;' if label in person_columns else ''}'>"
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
                f"{'min-width:45px;' if label in narrow_columns else ''}"
                f"{'min-width:50px;' if label in person_columns else ''}'>"
                f"{html.escape(row.get(label, ''))}</td>"
            )
            for label in headers
        )
        body_rows.append(f"<tr>{cells}</tr>")

    if not body_rows:
        body_rows.append(
            f"<tr><td colspan='{len(headers)}' style='border:1px solid #cfcfcf;padding:8px;'>"
            "No records matched the filter."
            "</td></tr>"
        )

    return (
        "<table style='border-collapse:collapse;font-family:Segoe UI,Arial,sans-serif;font-size:12px;table-layout:auto;'>"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def build_subject(year: int, kw: str) -> str:
    return f"{year} {kw}欧洲技术外勤及售后备品使用情况 {kw} Onsite Service"


def build_body(year: int, kw: str, people_text: str, table_html: str) -> str:
    return (
        "<p style='font-family:Segoe UI,Arial,sans-serif;font-size:12px;'>"
        "Dear All,<br><br>"
        f"下表是{year} {kw}欧洲技术外勤及售后备品使用情况，由 {html.escape(people_text)} 执行：<br>"
        f"the onsite Service in {year} {kw} was carried out by {html.escape(people_text)}, "
        "the details are following:"
        "</p>"
        + table_html
    )


def infer_name_from_profile(profile: Dict[str, Any]) -> str:
    given_name = (profile.get("givenName") or "").strip()
    surname = (profile.get("surname") or "").strip()
    if given_name or surname:
        return f"{given_name} {surname}".strip()

    display_name = (profile.get("displayName") or "").strip()
    if display_name:
        return display_name

    principal = (profile.get("mail") or profile.get("userPrincipalName") or "").strip()
    local_part = principal.split("@")[0]
    if "." in local_part:
        return " ".join(part.capitalize() for part in local_part.split(".") if part)
    return local_part or "First name Surname"


def build_signature_html(profile: Dict[str, Any]) -> str:
    name = infer_name_from_profile(profile)
    disclaimer_style = "font-family:Segoe UI,Arial,sans-serif;font-size:10px;color:#555555;"
    return (
        "<p style='font-family:Segoe UI,Arial,sans-serif;font-size:12px;'>"
        "Bei weiteren Anliegen stehen wir Ihnen gerne zur Verfugung.<br><br>"
        "Mit freundlichen Grussen/Best regards<br><br>"
        f"{html.escape(name)}<br><br>"
        "European Business Unit (BUEU)"
        "</p>"
        "<br><hr style='border:none;border-top:1px solid #999999;'><br>"
        f"<p style='{disclaimer_style}'>"
        "Alpha ESS Europe GmbH | Alfred-Herrhausen-Allee 3-5 | 65760 Eschborn | Deutschland<br><br>"
        "Amtsgericht Frankfurt am Main, HRB 101992, Geschäftsführer: Jun Wang, Boxun Xi<br><br>"
        "WEEE-Reg.-Nr. DE 27971023<br><br>"
        "Bitte prüfen Sie, ob diese Mail wirklich ausgedruckt werden muss!<br><br>"
        "Diese E-Mail enthält vertrauliche und/oder rechtlich geschützte Informationen. "
        "Wenn Sie nicht der richtige Adressat sind oder diese E-Mail irrtümlich erhalten haben, "
        "informieren Sie bitte sofort den Absender und vernichten Sie diese Mail. Das unerlaubte Kopieren "
        "sowie die unbefugte Weitergabe dieser Mail ist nicht gestattet.<br><br>"
        "This e-mail may contain confidential and/or privileged information. If you are not the intended recipient "
        "(or have received this e-mail in error) please notify the sender immediately and destroy this e-mail. "
        "Any unauthorized copying, disclosure or distribution of the material in this e-mail is strictly forbidden."
        "</p>"
    )


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Onsite Service Mailer")
        self.root.geometry("760x660")
        self.records: List[Dict[str, Any]] = []
        self.filtered_records: List[Dict[str, Any]] = []

        self.kw_var = tk.StringVar(value="KW12")
        self.direction_var = tk.StringVar()
        self.onsite_var = tk.StringVar(value="yes")
        self.subject_var = tk.StringVar(value="")
        self.subject_edited = False
        self.to_var = tk.StringVar(value="")
        self.cc_var = tk.StringVar(value="")
        self.to_technik_var = tk.BooleanVar(value=True)
        self.cc_logistik_var = tk.BooleanVar(value=True)
        self.cc_ming_var = tk.BooleanVar(value=True)
        self.cc_service_var = tk.BooleanVar(value=True)
        self.count_var = tk.StringVar(value="命中记录数: 未查询")
        self.status_var = tk.StringVar(value="准备就绪。")
        self.device_code_window: tk.Toplevel | None = None
        self.device_code_value_var = tk.StringVar(value="")
        self.device_code_url_var = tk.StringVar(value="")
        self.pending_device_code_url = ""
        self.attachment_paths: List[str] = []

        container = ttk.Frame(root, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="周数 (例如 KW12)").grid(row=0, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.kw_var, width=20).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(container, text="方向").grid(row=1, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.direction_var, width=20).grid(row=1, column=1, sticky="ew", pady=4)
        direction_options = ttk.Frame(container)
        direction_options.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        for index, option in enumerate(DEFAULT_DIRECTIONS):
            ttk.Button(
                direction_options,
                text=option,
                command=lambda value=option: self.direction_var.set(value),
            ).grid(row=index // 4, column=index % 4, padx=3, pady=3, sticky="ew")
        for col in range(4):
            direction_options.columnconfigure(col, weight=1)

        ttk.Label(container, text="邮件标题").grid(row=3, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.subject_var).grid(row=3, column=1, sticky="ew", pady=4)

        ttk.Label(container, text="收件人").grid(row=4, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.to_var).grid(row=4, column=1, sticky="ew", pady=4)
        to_options = ttk.Frame(container)
        to_options.grid(row=5, column=1, sticky="w")
        ttk.Checkbutton(
            to_options,
            text="technik.service@alpha-ess.de",
            variable=self.to_technik_var,
        ).pack(side="left")

        ttk.Label(container, text="抄送").grid(row=6, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.cc_var).grid(row=6, column=1, sticky="ew", pady=4)
        cc_options = ttk.Frame(container)
        cc_options.grid(row=7, column=1, sticky="w")
        ttk.Checkbutton(
            cc_options,
            text="tech.logistik@alpha-ess.de",
            variable=self.cc_logistik_var,
        ).pack(side="left")
        ttk.Checkbutton(
            cc_options,
            text="ming.zhou@alpha-ess.com",
            variable=self.cc_ming_var,
        ).pack(side="left")
        ttk.Checkbutton(
            cc_options,
            text="service@alpha-ess.de",
            variable=self.cc_service_var,
        ).pack(side="left")

        ttk.Label(container, text="是否已上门").grid(row=8, column=0, sticky="w")
        onsite_frame = ttk.Frame(container)
        onsite_frame.grid(row=8, column=1, sticky="w", pady=4)
        ttk.Radiobutton(onsite_frame, text="是", variable=self.onsite_var, value="yes").pack(side="left")
        ttk.Radiobutton(onsite_frame, text="否", variable=self.onsite_var, value="no").pack(side="left")

        attachment_row = ttk.Frame(container)
        attachment_row.grid(row=9, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Button(attachment_row, text="选择附件", command=self.choose_attachments).pack(side="left")
        ttk.Button(attachment_row, text="清空附件", command=self.clear_attachments).pack(side="left", padx=(8, 0))

        self.attachment_label = ttk.Label(container, text="附件: 未选择")
        self.attachment_label.grid(row=10, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Button(container, text="查询记录", command=self.fetch_records).grid(row=11, column=0, pady=12, sticky="ew")
        ttk.Button(container, text="确认并发邮件", command=self.send_email).grid(row=11, column=1, pady=12, sticky="ew")

        ttk.Label(container, textvariable=self.count_var).grid(row=12, column=0, columnspan=2, sticky="w", pady=4)

        self.preview = tk.Text(container, height=8, wrap="word")
        self.preview.grid(row=13, column=0, columnspan=2, sticky="nsew", pady=8)
        self.preview.insert("1.0", "这里会显示查询结果预览。")
        self.preview.config(state="disabled")

        ttk.Label(container, textvariable=self.status_var, foreground="#555555").grid(
            row=14, column=0, columnspan=2, sticky="w", pady=4
        )

        container.columnconfigure(1, weight=1)
        container.rowconfigure(13, weight=1)
        self.kw_var.trace_add("write", self.on_kw_changed)
        self.subject_var.trace_add("write", self.on_subject_changed)
        self.refresh_subject()

    def set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.root.update_idletasks()

    def default_subject(self) -> str:
        kw = self.kw_var.get().strip().upper() or "KWxx"
        year = datetime.now(GERMANY_TZ).year if GERMANY_TZ is not None else datetime.now().year
        return build_subject(year, kw)

    def refresh_subject(self) -> None:
        if not self.subject_edited:
            self.subject_var.set(self.default_subject())

    def on_kw_changed(self, *_args) -> None:
        self.refresh_subject()

    def on_subject_changed(self, *_args) -> None:
        current = self.subject_var.get().strip()
        default = self.default_subject()
        self.subject_edited = current != "" and current != default

    def run_on_ui(self, func, *args) -> None:
        self.root.after(0, lambda: func(*args))

    def set_preview(self, text: str) -> None:
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.config(state="disabled")

    def show_device_code(self, code: str, url: str) -> None:
        self.pending_device_code_url = url
        if self.device_code_window is None or not self.device_code_window.winfo_exists():
            window = tk.Toplevel(self.root)
            window.title("Microsoft 365 Device Code")
            window.geometry("520x220")
            window.resizable(False, False)
            self.device_code_window = window

            ttk.Label(
                window,
                text="请打开下面网址并输入设备代码登录",
            ).pack(anchor="w", padx=16, pady=(16, 8))

            url_entry = ttk.Entry(window, textvariable=self.device_code_url_var, state="readonly")
            url_entry.pack(fill="x", padx=16)

            ttk.Label(window, text="设备代码").pack(anchor="w", padx=16, pady=(16, 4))
            code_label = ttk.Label(window, textvariable=self.device_code_value_var, font=("Segoe UI", 24, "bold"))
            code_label.pack(anchor="center", pady=8)

            button_row = ttk.Frame(window)
            button_row.pack(fill="x", padx=16, pady=8)
            ttk.Button(button_row, text="复制代码并打开网页", command=self.copy_device_code).pack(side="left")
            ttk.Button(button_row, text="关闭", command=window.destroy).pack(side="right")

            ttk.Label(
                window,
                text="浏览器登录完成后，此窗口可直接关闭，主程序会自动继续。",
                foreground="#555555",
            ).pack(anchor="w", padx=16, pady=(4, 0))

        self.device_code_value_var.set(code)
        self.device_code_url_var.set(url)
        assert self.device_code_window is not None
        self.device_code_window.deiconify()
        self.device_code_window.lift()
        self.device_code_window.focus_force()

    def close_device_code(self) -> None:
        if self.device_code_window is not None and self.device_code_window.winfo_exists():
            self.device_code_window.destroy()
        self.device_code_window = None

    def copy_device_code(self) -> None:
        code = self.device_code_value_var.get().strip()
        if not code:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        if self.pending_device_code_url:
            try:
                webbrowser.open(self.pending_device_code_url)
            except Exception:
                pass
        self.set_status("设备代码已复制到剪贴板，并已打开认证网页。")

    def choose_attachments(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择附件",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not paths:
            return
        for path in paths:
            if path not in self.attachment_paths:
                self.attachment_paths.append(path)
        self.refresh_attachment_label()

    def clear_attachments(self) -> None:
        self.attachment_paths = []
        self.refresh_attachment_label()

    def refresh_attachment_label(self) -> None:
        if not self.attachment_paths:
            self.attachment_label.config(text="附件: 未选择")
            return
        names = ", ".join(Path(path).name for path in self.attachment_paths)
        self.attachment_label.config(text=f"附件({len(self.attachment_paths)}): {names}")

    def fetch_records(self) -> None:
        kw = self.kw_var.get().strip().upper()
        direction = self.direction_var.get().strip()
        if not kw or not direction:
            messagebox.showwarning("缺少输入", "请输入周数和方向。")
            return
        self.set_status("正在从飞书读取记录...")
        threading.Thread(target=self._fetch_records_worker, args=(kw, direction), daemon=True).start()

    def _fetch_records_worker(self, kw: str, direction: str) -> None:
        try:
            records = FeishuClient().list_records()
            filtered_records = [record for record in records if record_matches(record, kw, direction)]
            people = collect_people(filtered_records) or "无"
            preview_lines = [
                f"周数: {kw}",
                f"方向: {direction}",
                f"记录数: {len(filtered_records)}",
                f"人员: {people}",
            ]
            if filtered_records:
                sample = filtered_records[0]
                preview_lines.extend(
                    [
                        "",
                        "首条记录预览:",
                        f"上门单号: {format_field_value('上门单号', sample.get('上门单号'))}",
                        f"日期: {format_field_value('日期', sample.get('日期'))}",
                        f"状态: {format_field_value('状态', sample.get('状态'))}",
                    ]
                )
            self.records = records
            self.filtered_records = filtered_records
            self.run_on_ui(self.count_var.set, f"命中记录数: {len(filtered_records)}")
            self.run_on_ui(self.set_preview, "\n".join(preview_lines))
            self.run_on_ui(self.set_status, "查询完成。请确认记录数量是否正确。")
        except Exception as exc:
            self.run_on_ui(self.set_status, "查询失败。")
            self.run_on_ui(messagebox.showerror, "查询失败", str(exc))

    def send_email(self) -> None:
        if not self.filtered_records:
            messagebox.showwarning("无记录", "请先查询并确认有命中记录。")
            return

        confirmed = messagebox.askyesno("确认数量", f"当前命中 {len(self.filtered_records)} 条记录，数量是否正确？")
        if not confirmed:
            return

        include_onsite_details = self.onsite_var.get() == "yes"
        kw = self.kw_var.get().strip().upper()
        to_addresses = [item.strip() for item in self.to_var.get().split(",") if item.strip()]
        cc_addresses = [item.strip() for item in self.cc_var.get().split(",") if item.strip()]
        if self.to_technik_var.get() and "technik.service@alpha-ess.de" not in to_addresses:
            to_addresses.append("technik.service@alpha-ess.de")
        if self.cc_logistik_var.get() and "tech.logistik@alpha-ess.de" not in cc_addresses:
            cc_addresses.append("tech.logistik@alpha-ess.de")
        if self.cc_ming_var.get() and "ming.zhou@alpha-ess.com" not in cc_addresses:
            cc_addresses.append("ming.zhou@alpha-ess.com")
        if self.cc_service_var.get() and "service@alpha-ess.de" not in cc_addresses:
            cc_addresses.append("service@alpha-ess.de")
        if not to_addresses:
            messagebox.showwarning("缺少收件人", "请至少填写一个收件人。")
            return

        year = infer_year(self.filtered_records)
        people_text = collect_people(self.filtered_records) or "N/A"
        rows = [project_record(record, include_onsite_details) for record in self.filtered_records]
        subject = self.subject_var.get().strip() or build_subject(year, kw)
        body = build_body(year, kw, people_text, build_html_table(rows, include_onsite_details))

        threading.Thread(
            target=self._send_email_worker,
            args=(subject, body, to_addresses, cc_addresses, list(self.attachment_paths)),
            daemon=True,
        ).start()

    def _send_email_worker(
        self,
        subject: str,
        body: str,
        to_addresses: List[str],
        cc_addresses: List[str],
        attachment_paths: List[str],
    ) -> None:
        try:
            self.run_on_ui(self.set_status, "正在申请 Microsoft 365 登录...")
            mailer = GraphMailer()
            access_token = mailer.acquire_token(
                lambda text: self.run_on_ui(self.set_status, text),
                lambda code, url: self.run_on_ui(self.show_device_code, code, url),
            )
            self.run_on_ui(self.close_device_code)
            profile = mailer.get_user_profile(access_token)
            full_body = body + build_signature_html(profile)
            self.run_on_ui(self.set_status, "正在发送邮件...")
            mailer.send_mail(access_token, subject, full_body, to_addresses, cc_addresses, attachment_paths)
            self.run_on_ui(self.set_status, "邮件发送成功。")
            self.run_on_ui(messagebox.showinfo, "完成", f"邮件已发送。\n收件人: {', '.join(to_addresses)}")
        except Exception as exc:
            self.run_on_ui(self.close_device_code)
            self.run_on_ui(self.set_status, "发送失败。")
            self.run_on_ui(messagebox.showerror, "发送失败", str(exc))


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
