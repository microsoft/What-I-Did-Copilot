"""
email_send.py — Send HTML email via Outlook COM automation (PowerShell).
No extra packages required. Works on any Windows machine with Outlook installed.
"""
import os
import subprocess
import tempfile


def send_email(to: str, subject: str, html_body: str) -> bool:
    """
    Send an HTML email using Outlook via PowerShell COM automation.
    Writes the HTML to a temp file to avoid quoting/escaping issues.
    Returns True on success.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".html", prefix="whatididghcp_")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(html_body)

        safe_subject = subject.replace("'", "''")
        safe_to      = to.replace("'", "''")
        safe_path    = tmp_path.replace("\\", "\\\\")

        ps_script = f"""
try {{
    $htmlBody = Get-Content -Path '{safe_path}' -Raw -Encoding UTF8
    $outlook   = New-Object -ComObject Outlook.Application
    $mail      = $outlook.CreateItem(0)
    $mail.To       = '{safe_to}'
    $mail.Subject  = '{safe_subject}'
    $mail.HTMLBody = $htmlBody
    $mail.Send()
    Write-Output 'SUCCESS'
}} catch {{
    Write-Error $_.Exception.Message
    exit 1
}}
"""
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if "SUCCESS" in result.stdout:
            return True
        if result.returncode != 0:
            print(f"PowerShell error: {result.stderr.strip()}")
        return False

    except subprocess.TimeoutExpired:
        print("Outlook did not respond within 30 seconds.")
        return False
    except Exception as e:
        print(f"Email send error: {e}")
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
