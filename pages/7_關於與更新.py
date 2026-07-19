from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.services.update_service import (
    UpdateInfo,
    check_and_cache_update,
    download_update,
    launch_update_installer,
    read_cached_update_status,
)
from src.version import __version__


st.set_page_config(
    page_title="關於與更新",
    page_icon="⬆️",
    layout="wide",
)

st.title("⬆️ 關於與更新")
st.metric("目前版本", __version__)

if st.button("立即檢查更新", type="primary"):
    with st.spinner("正在檢查更新..."):
        st.session_state["update_status"] = check_and_cache_update()

status = st.session_state.get("update_status") or read_cached_update_status()
if status:
    state = status.get("status")
    if state == "available":
        update = status.get("update") or {}
        st.success(f"發現新版本：{update.get('version')}")
        if update.get("release_notes"):
            st.markdown("### 更新內容")
            st.write(update["release_notes"])

        installer_path = status.get("downloaded_installer")
        if not installer_path:
            if st.button("下載並驗證更新"):
                with st.spinner("正在下載並驗證 SHA-256..."):
                    try:
                        installer = download_update(UpdateInfo(**update))
                        status["downloaded_installer"] = str(installer)
                        st.session_state["update_status"] = status
                        st.rerun()
                    except Exception as error:
                        st.error(f"更新下載失敗：{error}")
        else:
            path = Path(installer_path)
            if path.exists():
                st.success("更新安裝檔已下載並通過 SHA-256 驗證。")
                if st.button("安裝更新並重新啟動", type="primary"):
                    try:
                        launch_update_installer(path)
                        st.info("安裝程式已啟動，應用程式將由安裝程式關閉並更新。")
                    except Exception as error:
                        st.error(f"無法啟動更新安裝程式：{error}")
            else:
                st.warning("先前下載的安裝檔已不存在，請重新檢查更新。")
    elif state == "current":
        st.success("目前已是最新版本。")
    elif state == "error":
        st.warning(f"更新檢查失敗：{status.get('message')}")
    elif state == "disabled":
        st.caption(str(status.get("message") or "自動更新尚未啟用。"))
    elif state == "not_published":
        st.info("GitHub 尚未發布任何正式版本，目前沒有可下載的更新。")

st.divider()
st.subheader("更新安全機制")
st.markdown(
    "- 更新來源固定為本專案的 GitHub Releases，不讀取使用者提供的網址。\n"
    "- 只接受名稱完全相符的 Windows 安裝檔。\n"
    "- 下載完成後必須符合 GitHub 提供的 SHA-256 digest。\n"
    "- 安裝前仍由使用者確認，不會在背景無聲執行未知程式。"
)
