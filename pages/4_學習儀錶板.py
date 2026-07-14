from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from src.services.learning_dashboard_service import (
    get_learning_dashboard_data,
    get_learning_documents,
)


st.set_page_config(
    page_title="學習儀表板",
    page_icon="📊",
    layout="wide",
)


def inject_full_text_css() -> None:
    """避免 Streamlit 元件文字被省略號截斷。"""

    st.markdown(
        """
        <style>
        html,
        body,
        [class*="css"] {
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        div[data-testid="stMarkdownContainer"],
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stCaptionContainer"],
        div[data-testid="stText"] {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        div[data-testid="stMetric"] {
            min-width: 0 !important;
            height: auto !important;
            overflow: visible !important;
        }

        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] label p,
        div[data-testid="stMetric"] [data-testid="stMetricLabel"],
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] p,
        div[data-testid="stMetric"] [data-testid="stMetricValue"],
        div[data-testid="stMetric"] [data-testid="stMetricValue"] div {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
            line-height: 1.35 !important;
            max-width: none !important;
            height: auto !important;
        }

        div[data-baseweb="select"] span,
        div[data-baseweb="select"] div,
        div[data-baseweb="popover"] span,
        div[data-baseweb="popover"] div,
        li[role="option"] {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
            height: auto !important;
        }

        button,
        button div,
        button p,
        a,
        a div,
        a p {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
            height: auto !important;
        }

        details summary,
        details summary span,
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary p {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        .dashboard-card {
            border: 1px solid rgba(128, 128, 128, 0.24);
            border-radius: 16px;
            padding: 18px;
            margin-bottom: 14px;
            background: rgba(127, 127, 127, 0.04);
        }

        .dashboard-title {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .dashboard-subtitle {
            font-size: 0.92rem;
            opacity: 0.72;
            line-height: 1.5;
        }

        .weak-active {
            color: #d9534f;
            font-weight: 700;
        }

        .weak-improving {
            color: #f0ad4e;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_full_text_css()


def safe_text(value, default: str = "") -> str:
    """安全轉換為字串。"""

    if value is None:
        return default

    try:
        return str(value)
    except Exception:
        return default


def safe_int(value, default: int = 0) -> int:
    """安全轉換為整數。"""

    try:
        if value is None:
            return default

        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value, default: float = 0.0) -> float:
    """安全轉換為浮點數。"""

    try:
        if value is None:
            return default

        return float(value)
    except (TypeError, ValueError):
        return default


def format_datetime(value) -> str:
    """格式化日期時間。"""

    if value is None:
        return "未知時間"

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    return safe_text(value, "未知時間")


def build_document_options(
    documents: list[dict],
) -> dict[str, str]:
    """建立文件下拉選單。"""

    options: dict[str, str] = {}
    name_counts: dict[str, int] = {}

    for document in documents:
        file_name = safe_text(
            document.get("file_name"),
            "未命名文件",
        )

        name_counts[file_name] = (
            name_counts.get(file_name, 0) + 1
        )

    for document in documents:
        file_name = safe_text(
            document.get("file_name"),
            "未命名文件",
        )

        label = file_name

        if name_counts.get(file_name, 0) > 1:
            label = (
                f"{file_name}（更新："
                f"{format_datetime(document.get('updated_at'))}）"
            )

        options[label] = safe_text(
            document.get("id")
        )

    return options


def show_top_metrics(
    dashboard_data: dict,
) -> None:
    """顯示儀表板主要指標。"""

    overview = dashboard_data.get(
        "overview",
        {},
    )

    quiz = overview.get(
        "quiz",
        {},
    )

    flashcard = overview.get(
        "flashcard",
        {},
    )

    weak_points = overview.get(
        "weak_points",
        {},
    )

    row1_col1, row1_col2, row1_col3, row1_col4 = (
        st.columns(4)
    )

    row1_col1.metric(
        "學習健康分數",
        (
            f"{safe_float(dashboard_data.get('learning_health_score'))}"
            " / 100"
        ),
    )

    row1_col2.metric(
        "累積學習操作",
        safe_int(
            dashboard_data.get(
                "total_learning_actions"
            )
        ),
    )

    row1_col3.metric(
        "優先複習項目",
        safe_int(
            dashboard_data.get(
                "priority_review_count"
            )
        ),
    )

    row1_col4.metric(
        "尚未改善弱點",
        safe_int(
            weak_points.get(
                "active_count"
            )
        ),
    )

    row2_col1, row2_col2, row2_col3, row2_col4 = (
        st.columns(4)
    )

    row2_col1.metric(
        "Quiz 得分率",
        f"{safe_float(quiz.get('score_rate'))}%",
    )

    row2_col2.metric(
        "Quiz 正確率",
        f"{safe_float(quiz.get('accuracy'))}%",
    )

    row2_col3.metric(
        "Flash Card 完成率",
        (
            f"{safe_float(flashcard.get('completion_rate'))}"
            "%"
        ),
    )

    row2_col4.metric(
        "今日到期卡片",
        safe_int(
            flashcard.get(
                "due_count"
            )
        ),
    )


def show_quiz_section(
    quiz: dict,
) -> None:
    """顯示 Quiz 統計區塊。"""

    st.subheader("🧠 Quiz 表現")

    metric_col1, metric_col2, metric_col3, metric_col4 = (
        st.columns(4)
    )

    metric_col1.metric(
        "題目數",
        safe_int(
            quiz.get("quiz_count")
        ),
    )

    metric_col2.metric(
        "作答次數",
        safe_int(
            quiz.get("attempt_count")
        ),
    )

    metric_col3.metric(
        "答對",
        safe_int(
            quiz.get("correct_count")
        ),
    )

    metric_col4.metric(
        "答錯",
        safe_int(
            quiz.get("wrong_count")
        ),
    )

    chart_data = pd.DataFrame(
        {
            "自評結果": [
                "答對",
                "部分答對",
                "答錯",
            ],
            "次數": [
                safe_int(
                    quiz.get(
                        "correct_count"
                    )
                ),
                safe_int(
                    quiz.get(
                        "partial_count"
                    )
                ),
                safe_int(
                    quiz.get(
                        "wrong_count"
                    )
                ),
            ],
        }
    )

    st.bar_chart(
        chart_data,
        x="自評結果",
        y="次數",
        use_container_width=True,
    )


def show_flashcard_section(
    flashcard: dict,
) -> None:
    """顯示 Flash Card 統計區塊。"""

    st.subheader("🗂️ Flash Card 進度")

    metric_col1, metric_col2, metric_col3, metric_col4 = (
        st.columns(4)
    )

    metric_col1.metric(
        "卡片總數",
        safe_int(
            flashcard.get(
                "flashcard_count"
            )
        ),
    )

    metric_col2.metric(
        "已複習卡片",
        safe_int(
            flashcard.get(
                "reviewed_flashcard_count"
            )
        ),
    )

    metric_col3.metric(
        "未複習卡片",
        safe_int(
            flashcard.get(
                "unreviewed_count"
            )
        ),
    )

    metric_col4.metric(
        "平均熟悉度",
        (
            f"{safe_float(flashcard.get('average_familiarity_score'))}"
            " / 5"
        ),
    )

    score_counts = flashcard.get(
        "score_counts",
        {},
    )

    familiarity_data = pd.DataFrame(
        {
            "熟悉度": [
                "0 完全不熟",
                "1 很不熟",
                "2 有點不熟",
                "3 普通",
                "4 熟悉",
                "5 非常熟悉",
            ],
            "次數": [
                safe_int(score_counts.get(0)),
                safe_int(score_counts.get(1)),
                safe_int(score_counts.get(2)),
                safe_int(score_counts.get(3)),
                safe_int(score_counts.get(4)),
                safe_int(score_counts.get(5)),
            ],
        }
    )

    st.bar_chart(
        familiarity_data,
        x="熟悉度",
        y="次數",
        use_container_width=True,
    )


def show_priority_review(
    dashboard_data: dict,
) -> None:
    """顯示優先複習區塊。"""

    overview = dashboard_data.get(
        "overview",
        {},
    )

    flashcard = overview.get(
        "flashcard",
        {},
    )

    weak_points = overview.get(
        "weak_points",
        {},
    )

    st.subheader("🔥 優先複習")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="dashboard-card">
                <div class="dashboard-title">
                    今日到期 Flash Cards
                </div>
                <div class="dashboard-subtitle">
                    已到期或尚未建立排程的卡片，建議優先完成複習。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.metric(
            "到期數量",
            safe_int(
                flashcard.get(
                    "due_count"
                )
            ),
        )

    with col2:
        st.markdown(
            """
            <div class="dashboard-card">
                <div class="dashboard-title">
                    仍然不熟的 Quiz 重點
                </div>
                <div class="dashboard-subtitle">
                    弱點狀態仍為 active 的題目，建議重新閱讀解析並再次作答。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.metric(
            "不熟數量",
            safe_int(
                weak_points.get(
                    "active_count"
                )
            ),
        )


def show_weak_point_ranking(
    weak_points: dict,
) -> None:
    """顯示弱點排行。"""

    st.subheader("📌 弱點排行")

    items = weak_points.get(
        "items",
        [],
    )

    if not items:
        st.success(
            "目前沒有需要優先處理的弱點。"
        )
        return

    sorted_items = sorted(
        items,
        key=lambda item: (
            safe_int(
                item.get(
                    "weakness_score"
                )
            ),
            safe_int(
                item.get(
                    "wrong_count"
                )
            ),
        ),
        reverse=True,
    )

    for index, item in enumerate(
        sorted_items,
        start=1,
    ):
        status = safe_text(
            item.get("status")
        )

        status_label = (
            "仍然不熟"
            if status == "active"
            else "正在改善"
        )

        status_class = (
            "weak-active"
            if status == "active"
            else "weak-improving"
        )

        st.markdown(
            (
                '<div class="dashboard-card">'
                f'<div class="dashboard-title">'
                f'{index}. {safe_text(item.get("question"))}'
                '</div>'
                f'<div class="{status_class}">'
                f'{status_label}'
                '</div>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )

        metric_col1, metric_col2, metric_col3 = (
            st.columns(3)
        )

        metric_col1.metric(
            "弱點分數",
            safe_int(
                item.get(
                    "weakness_score"
                )
            ),
        )

        metric_col2.metric(
            "答錯次數",
            safe_int(
                item.get(
                    "wrong_count"
                )
            ),
        )

        metric_col3.metric(
            "部分答對",
            safe_int(
                item.get(
                    "partial_count"
                )
            ),
        )

        with st.expander(
            "查看答案與解析"
        ):
            st.write("**最近回答：**")
            st.write(
                safe_text(
                    item.get(
                        "last_answer"
                    ),
                    "尚無紀錄",
                )
            )

            st.write("**標準答案：**")
            st.write(
                safe_text(
                    item.get(
                        "correct_answer"
                    )
                )
            )

            explanation = safe_text(
                item.get("explanation")
            ).strip()

            if explanation:
                st.write("**解析：**")
                st.write(explanation)

        st.caption(
            "章節："
            f"{safe_text(item.get('chapter_title'), '未分類章節')}｜"
            "最後更新："
            f"{format_datetime(item.get('updated_at'))}"
        )

        st.divider()


def show_recent_activity(
    activities: list[dict],
) -> None:
    """顯示近期學習活動。"""

    st.subheader("🕘 近期學習活動")

    if not activities:
        st.info(
            "目前還沒有 Quiz 或 Flash Card 的學習紀錄。"
        )
        return

    for index, activity in enumerate(
        activities,
        start=1,
    ):
        activity_type = safe_text(
            activity.get(
                "activity_type"
            )
        )

        icon = (
            "🧠"
            if activity_type == "quiz"
            else "🗂️"
        )

        with st.expander(
            (
                f"{icon} 第 {index} 筆｜"
                f"{safe_text(activity.get('title'))}"
            )
        ):
            st.write(
                "**活動類型：** "
                f"{safe_text(activity.get('activity_label'))}"
            )

            st.write(
                "**結果：** "
                f"{safe_text(activity.get('result'))}"
            )

            st.write(
                "**分數：** "
                f"{safe_int(activity.get('score'))}"
                " / "
                f"{safe_int(activity.get('max_score'))}"
            )

            st.caption(
                "章節："
                f"{safe_text(activity.get('chapter_title'), '未分類章節')}｜"
                "時間："
                f"{format_datetime(activity.get('occurred_at'))}"
            )


st.title("📊 學習儀表板")
st.caption(
    "整合 Quiz、錯題、不熟重點與 Flash Card 複習進度。"
)

try:
    documents = get_learning_documents()
except Exception as error:
    st.error(
        f"讀取學習文件失敗：{error}"
    )
    st.stop()

if not documents:
    st.info(
        "目前沒有可顯示的學習資料。"
        "請先生成 Quiz 或 Flash Cards，"
        "並確認資料已寫入 SQLite。"
    )
    st.stop()

document_options = build_document_options(
    documents
)

selected_document_label = st.selectbox(
    "選擇文件",
    options=list(
        document_options.keys()
    ),
)

selected_document_id = (
    document_options[
        selected_document_label
    ]
)

selected_document = next(
    (
        item
        for item in documents
        if safe_text(
            item.get("id")
        )
        == selected_document_id
    ),
    {},
)

try:
    dashboard_data = get_learning_dashboard_data(
        document_id=selected_document_id,
        activity_limit=10,
    )
except Exception as error:
    st.error(
        f"讀取儀表板資料失敗：{error}"
    )
    st.stop()

st.markdown(
    (
        '<div class="dashboard-card">'
        '<div class="dashboard-title">'
        f'{safe_text(selected_document.get("file_name"), "未命名文件")}'
        '</div>'
        '<div class="dashboard-subtitle">'
        f'Quiz：{safe_int(selected_document.get("quiz_count"))} 題｜'
        f'Flash Cards：{safe_int(selected_document.get("flashcard_count"))} 張｜'
        f'章節：{safe_int(selected_document.get("chapter_count"))} 個'
        '</div>'
        '</div>'
    ),
    unsafe_allow_html=True,
)

show_top_metrics(
    dashboard_data
)

st.divider()

overview = dashboard_data.get(
    "overview",
    {},
)

quiz = overview.get(
    "quiz",
    {},
)

flashcard = overview.get(
    "flashcard",
    {},
)

weak_points = overview.get(
    "weak_points",
    {},
)

tab_overview, tab_weak, tab_activity = st.tabs(
    [
        "學習總覽",
        "弱點排行",
        "近期活動",
    ]
)

with tab_overview:
    show_priority_review(
        dashboard_data
    )

    st.divider()

    quiz_col, flashcard_col = st.columns(2)

    with quiz_col:
        show_quiz_section(
            quiz
        )

    with flashcard_col:
        show_flashcard_section(
            flashcard
        )

with tab_weak:
    show_weak_point_ranking(
        weak_points
    )

with tab_activity:
    show_recent_activity(
        dashboard_data.get(
            "recent_activity",
            [],
        )
    )
