from __future__ import annotations

import streamlit as st

from src.database.init_db import initialize_database
from src.services.background_job_service import (
    delete_background_job,
    list_background_jobs,
    request_background_job_cancel,
)


st.set_page_config(
    page_title="背景工作",
    page_icon="⚙️",
    layout="wide",
)

issues = initialize_database()
if issues:
    st.error("SQLite Schema 需要更新，背景工作目前無法使用。")
    st.stop()

st.title("⚙️ 背景工作")
st.caption("AI 分析與 Notion 匯出會在獨立 Worker 執行。關閉瀏覽器不會刪除工作紀錄。")

status_filter = st.selectbox(
    "顯示狀態",
    ["全部", "等待中", "執行中", "已完成", "失敗", "已取消"],
)

status_map = {
    "等待中": "pending",
    "執行中": "running",
    "已完成": "completed",
    "失敗": "failed",
    "已取消": "cancelled",
}
label_map = {
    "pending": "等待中",
    "running": "執行中",
    "completed": "已完成",
    "failed": "失敗",
    "cancelled": "已取消",
}

@st.fragment(run_every="2s")
def render_background_jobs(selected_filter: str) -> None:
    jobs = list_background_jobs(limit=200)
    selected_status = status_map.get(selected_filter)
    if selected_status:
        jobs = [job for job in jobs if job["status"] == selected_status]

    if not jobs:
        st.info("目前沒有符合條件的背景工作。")
        return

    for job in jobs:
        job_id = str(job["id"])
        status = str(job["status"])
        with st.container(border=True):
            header_col, status_col = st.columns([4, 1])
            header_col.markdown(f"**{job['display_name']}**")
            status_col.markdown(f"**{label_map.get(status, status)}**")

            st.progress(
                int(job.get("progress_percent", 0)),
                text=str(job.get("progress_message") or ""),
            )
            st.caption(
                f"類型：{job['job_type']}｜Job ID：{job_id}｜"
                f"建立時間：{job.get('created_at')}"
            )

            if job.get("error_message"):
                st.error(str(job["error_message"]))

            action_col1, action_col2 = st.columns([1, 4])
            if status in {"pending", "running"}:
                if action_col1.button(
                    "要求取消",
                    key=f"cancel_job_{job_id}",
                    width="stretch",
                ):
                    request_background_job_cancel(job_id)
                    st.rerun(scope="fragment")
            elif action_col1.button(
                "刪除紀錄",
                key=f"delete_job_{job_id}",
                width="stretch",
            ):
                if delete_background_job(job_id):
                    st.rerun(scope="fragment")
                else:
                    st.warning("只有已完成、失敗或取消的工作可以刪除。")


render_background_jobs(status_filter)
