"""Windows Toast Notification Dispatcher.

Sends modern Windows desktop toast notifications, attempting system tray balloon
first, and falling back to native PowerShell Windows Runtime toasts.
"""

from __future__ import annotations
import os
import subprocess
import threading
from typing import Optional, Any


def send_toast_notification(
    title: str,
    message: str,
    tray_mgr: Optional[Any] = None,
) -> None:
    """Send an asynchronous, non-blocking toast notification on Windows."""
    def _deliver():
        # 1. If tray manager is active with an icon, deliver through pystray
        if tray_mgr is not None and getattr(tray_mgr, "_icon", None) and getattr(tray_mgr, "_is_running", False):
            try:
                tray_mgr.notify(message, title)
                return
            except Exception:
                pass

        # 2. Native Windows PowerShell toast notification fallback
        if os.name == "nt":
            try:
                clean_title = title.replace('"', '`"').replace("'", "`'")
                clean_msg = message.replace('"', '`"').replace("'", "`'")

                ps_script = (
                    f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
                    f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                    f"$textNodes = $template.GetElementsByTagName('text'); "
                    f"$textNodes.Item(0).AppendChild($template.CreateTextNode('{clean_title}')) | Out-Null; "
                    f"$textNodes.Item(1).AppendChild($template.CreateTextNode('{clean_msg}')) | Out-Null; "
                    f"$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Login Wallpaper Selector'); "
                    f"$notification = [Windows.UI.Notifications.ToastNotification]::new($template); "
                    f"$notifier.Show($notification);"
                )

                creation_flags = 0x08000000  # CREATE_NO_WINDOW
                subprocess.run(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                    creationflags=creation_flags,
                    timeout=5,
                    capture_output=True,
                )
            except Exception:
                pass

    threading.Thread(target=_deliver, daemon=True).start()
