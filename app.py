import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from openpyxl import Workbook
from openpyxl.styles import Font


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


def get_env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value or ""


def split_csv_env(name: str) -> List[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


class FeishuClient:
    def __init__(self) -> None:
        self.base_url = get_env("FEISHU_BASE_URL", "https://open.feishu.cn")
        self.app_id = get_env("FEISHU_APP_ID", required=True)
        self.app_secret = get_env("FEISHU_APP_SECRET", required=True)
        self.app_token = get_env("FEISHU_APP_TOKEN", required=True)
        self.table_id = get_env("FEISHU_TABLE_ID", required=True)
        self.view_id = get_env("FEISHU_VIEW_ID")
        self.page_size = int(get_env("FEISHU_PAGE_SIZE", "100"))
        self._tenant_access_token: Optional[str] = None

    def _request_tenant_token(self) -> str:
        url = f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal"
        response = requests.post(
            url,
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"Feishu auth failed: {payload}")
        return payload["tenant_access_token"]

    @property
    def tenant_access_token(self) -> str:
        if not self._tenant_access_token:
            self._tenant_access_token = self._request_tenant_token()
        return self._tenant_access_token

    def list_records(self) -> List[Dict[str, Any]]:
        url = (
            f"{self.base_url}/open-apis/bitable/v1/apps/{self.app_token}"
            f"/tables/{self.table_id}/records"
        )
        headers = {"Authorization": f"Bearer {self.tenant_access_token}"}
        page_token = ""
        records: List[Dict[str, Any]] = []

        while True:
            params: Dict[str, Any] = {"page_size": self.page_size}
            if page_token:
                params["page_token"] = page_token
            if self.view_id:
                params["view_id"] = self.view_id

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 0:
                raise RuntimeError(f"Feishu record query failed: {payload}")

            data = payload.get("data", {})
            items = data.get("items", [])
            for item in items:
                records.append(item.get("fields", {}))

            if not data.get("has_more"):
                break
            page_token = data.get("page_token", "")

        return records


def normalize_cell_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(normalize_cell_value(item) for item in value)
    if isinstance(value, dict):
        if "text" in value:
            return normalize_cell_value(value["text"])
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def infer_headers(records: Iterable[Dict[str, Any]]) -> List[str]:
    seen = []
    for record in records:
        for key in record.keys():
            if key not in seen:
                seen.append(key)
    return seen


def create_excel(records: List[Dict[str, Any]], headers: List[str], output_path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Feishu Report"

    worksheet.append(headers)
    for cell in worksheet[1]:
        cell.font = Font(bold=True)

    for record in records:
        worksheet.append([normalize_cell_value(record.get(header)) for header in headers])

    for column_cells in worksheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 50)

    workbook.save(output_path)


class GraphMailer:
    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self) -> None:
        self.tenant_id = get_env("GRAPH_TENANT_ID", "common")
        self.client_id = get_env("GRAPH_CLIENT_ID", DEFAULT_PUBLIC_CLIENT_ID)
        self.scope = "https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/User.Read offline_access"

    def acquire_token(self) -> str:
        base_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0"
        device_code_response = requests.post(
            f"{base_url}/devicecode",
            data={"client_id": self.client_id, "scope": self.scope},
            timeout=30,
        )
        device_code_response.raise_for_status()
        flow = device_code_response.json()
        if "device_code" not in flow:
            raise RuntimeError(f"Failed to create device flow: {flow}")

        print(flow.get("message", "Open the verification URL and enter the code shown."))

        interval = int(flow.get("interval", 5))
        expires_in = int(flow.get("expires_in", 900))
        deadline = time.time() + expires_in

        while time.time() < deadline:
            time.sleep(interval)
            token_response = requests.post(
                f"{base_url}/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": self.client_id,
                    "device_code": flow["device_code"],
                },
                timeout=30,
            )
            result = token_response.json()
            if "access_token" in result:
                return result["access_token"]

            error = result.get("error")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                interval += 5
                continue
            raise RuntimeError(f"Device code login failed: {result}")

        raise TimeoutError("Device code login timed out before authorization completed.")

    def send_mail(
        self,
        access_token: str,
        to_addresses: List[str],
        cc_addresses: List[str],
        subject: str,
        html_body: str,
        attachment_path: Path,
    ) -> None:
        with attachment_path.open("rb") as file_obj:
            attachment_bytes = base64.b64encode(file_obj.read()).decode("utf-8")

        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_body},
                "toRecipients": [{"emailAddress": {"address": item}} for item in to_addresses],
                "ccRecipients": [{"emailAddress": {"address": item}} for item in cc_addresses],
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": attachment_path.name,
                        "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "contentBytes": attachment_bytes,
                    }
                ],
            },
            "saveToSentItems": True,
        }

        response = requests.post(
            f"{self.GRAPH_BASE_URL}/me/sendMail",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )

        if response.status_code not in (200, 202):
            raise RuntimeError(f"Send mail failed: {response.status_code} {response.text}")


def main() -> None:
    feishu = FeishuClient()
    records = feishu.list_records()
    if not records:
        raise RuntimeError("No Feishu records returned; nothing to export.")

    configured_headers = split_csv_env("EXPORT_FIELDS")
    headers = configured_headers or infer_headers(records)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_prefix = get_env("REPORT_FILE_PREFIX", "feishu_report")
    output_path = Path(f"{report_prefix}_{timestamp}.xlsx")
    create_excel(records, headers, output_path)

    today = datetime.now().strftime("%Y-%m-%d")
    sender_name = get_env("MAIL_SENDER_NAME", "Sender")
    subject = get_env("MAIL_SUBJECT_TEMPLATE", "[Report] {date}").format(date=today)
    body = get_env(
        "MAIL_BODY_TEMPLATE",
        "Hello,<br><br>Please find the attached report for {date}.<br><br>Regards,<br>{sender_name}",
    ).format(date=today, sender_name=sender_name)

    to_addresses = split_csv_env("MAIL_TO")
    cc_addresses = split_csv_env("MAIL_CC")
    if not to_addresses:
        raise RuntimeError("MAIL_TO cannot be empty.")

    mailer = GraphMailer()
    access_token = mailer.acquire_token()
    mailer.send_mail(
        access_token=access_token,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        subject=subject,
        html_body=body,
        attachment_path=output_path,
    )

    print(f"Report created: {output_path}")
    print(f"Mail sent to: {', '.join(to_addresses)}")


if __name__ == "__main__":
    main()
