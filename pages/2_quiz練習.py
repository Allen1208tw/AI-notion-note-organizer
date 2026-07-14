from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.services.quiz_practice_service import (
    get_chapters_by_document,
    get_practice_documents,
    get_practice_summary,
    get_quiz_attempt_history,
    get_quizzes_by_chapter,
    get_weak_points,
    get_wrong_questions,
    save_quiz_attempt,
)


st.set_page_config(
    page_title="Quiz 練習",
    page_icon="🧠",
    layout="wide",
)


def inject_full_text_css() -> None:
    """避免 Streamlit 元件文字被省略號截斷。"""

    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
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

        div[data-testid="stMetric"],
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

        button,
        button div,
        button p,
        a,
        a div,
        a p,
        details summary,
        details summary span,
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary p {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
            height: auto !important;
        }

        textarea {
            white-space: pre-wrap !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        .quiz-card,
        .weak-point-card {
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 14px;
            background: rgba(127, 127, 127, 0.04);
        }

        .quiz-question {
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.6;
            margin-bottom: 8px;
        }

        .status-active { color: #d9534f; font-weight: 700; }
        .status-improving { color: #f0ad4e; font-weight: 700; }
        .status-mastered { color: #5cb85c; font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_full_text_css()


def safe_text(value, default: str = "") -> str:
    """安全轉成字串。"""

    if value is None:
        return default

    try:
        return str(value)
    except Exception:
        return default


def format_datetime(value) -> str:
    """格式化日期時間。"""

    if value is None:
        return "未知時間"

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    return safe_text(value, "未知時間")


def build_document_options(documents: list[dict]) -> dict[str, str]:
    """建立不顯示 ID 的文件選項。"""

    options: dict[str, str] = {}
    name_counts: dict[str, int] = {}

    for document in documents:
        file_name = safe_text(
            document.get("file_name"),
            "未命名文件",
        )
        name_counts[file_name] = name_counts.get(file_name, 0) + 1

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

        options[label] = safe_text(document.get("id"))

    return options


def build_chapter_options(chapters: list[dict]) -> dict[str, str]:
    """建立章節選項。"""

    options: dict[str, str] = {}

    for chapter in chapters:
        order = chapter.get("chapter_order", "?")
        title = safe_text(chapter.get("title"), "未命名章節")
        quiz_count = chapter.get("quiz_count", 0)
        label = f"Module {order}｜{title}｜{quiz_count} 題 Quiz"
        options[label] = safe_text(chapter.get("id"))

    return options


def get_status_label(status: str) -> str:
    """取得弱點狀態中文名稱。"""

    return {
        "active": "仍然不熟",
        "improving": "正在改善",
        "mastered": "已掌握",
    }.get(status, status or "未知")


def get_status_class(status: str) -> str:
    """取得弱點狀態 CSS class。"""

    return {
        "active": "status-active",
        "improving": "status-improving",
        "mastered": "status-mastered",
    }.get(status, "")


def show_summary_metrics(
    document_id: str,
    chapter_id: str | None = None,
) -> None:
    """顯示練習統計。"""

    summary = get_practice_summary(
        document_id=document_id,
        chapter_id=chapter_id,
    )

    row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
    row1_col1.metric("Quiz 題目數", summary.get("quiz_count", 0))
    row1_col2.metric("作答次數", summary.get("attempt_count", 0))
    row1_col3.metric("答對", summary.get("correct_count", 0))
    row1_col4.metric("學習得分率", f"{summary.get('score_rate', 0)}%")

    row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)
    row2_col1.metric("部分答對", summary.get("partial_count", 0))
    row2_col2.metric("答錯", summary.get("wrong_count", 0))
    row2_col3.metric(
        "仍然不熟",
        summary.get("active_weak_point_count", 0),
    )
    row2_col4.metric(
        "正在改善",
        summary.get("improving_weak_point_count", 0),
    )


def show_quiz_practice(document_id: str, chapter_id: str) -> None:
    """顯示 Quiz 練習內容。"""

    quizzes = get_quizzes_by_chapter(
        document_id=document_id,
        chapter_id=chapter_id,
    )

    if not quizzes:
        st.info("這個章節目前沒有可練習的 Quiz。")
        return

    show_summary_metrics(
        document_id=document_id,
        chapter_id=chapter_id,
    )

    st.divider()

    for index, quiz in enumerate(quizzes, start=1):
        quiz_id = safe_text(quiz.get("id"))
        answer_key = f"quiz_answer_{quiz_id}"
        reveal_key = f"quiz_reveal_{quiz_id}"

        st.markdown(
            (
                '<div class="quiz-card">'
                '<div class="quiz-question">'
                f'第 {index} 題｜{safe_text(quiz.get("question"))}'
                '</div></div>'
            ),
            unsafe_allow_html=True,
        )

        meta_col1, meta_col2 = st.columns(2)
        meta_col1.caption(
            f"難度：{safe_text(quiz.get('difficulty'), 'medium')}"
        )
        meta_col2.caption(
            f"歷史作答次數：{quiz.get('attempt_count', 0)}"
        )

        user_answer = st.text_area(
            "輸入你的答案",
            key=answer_key,
            height=130,
            placeholder="先用自己的話回答，再查看標準答案並進行自評。",
        )

        is_revealed = st.session_state.get(
            reveal_key,
            False,
        )

        reveal_button_label = (
            "收合標準答案"
            if is_revealed
            else "查看標準答案"
        )

        if st.button(
            reveal_button_label,
            key=f"reveal_button_{quiz_id}",
            use_container_width=False,
        ):
            st.session_state[
                reveal_key
            ] = not is_revealed

            st.rerun()

        if st.session_state.get(
            reveal_key,
            False,
        ):
            st.success(
                "標準答案：\n\n"
                f"{safe_text(quiz.get('correct_answer'))}"
            )

            explanation = safe_text(quiz.get("explanation")).strip()

            if explanation:
                st.info(f"題目解析：\n\n{explanation}")

            st.markdown("#### 請進行自評")
            rating_col1, rating_col2, rating_col3 = st.columns(3)

            with rating_col1:
                correct_clicked = st.button(
                    "✅ 答對",
                    key=f"rate_correct_{quiz_id}",
                    use_container_width=True,
                    type="primary",
                )

            with rating_col2:
                partial_clicked = st.button(
                    "🟡 部分答對",
                    key=f"rate_partial_{quiz_id}",
                    use_container_width=True,
                )

            with rating_col3:
                wrong_clicked = st.button(
                    "❌ 答錯",
                    key=f"rate_wrong_{quiz_id}",
                    use_container_width=True,
                )

            selected_rating = None

            if correct_clicked:
                selected_rating = "correct"
            elif partial_clicked:
                selected_rating = "partial"
            elif wrong_clicked:
                selected_rating = "wrong"

            if selected_rating:
                try:
                    save_quiz_attempt(
                        quiz_id=quiz_id,
                        user_answer=user_answer,
                        self_rating=selected_rating,
                    )
                    st.success("作答紀錄已儲存，弱點資料已同步更新。")
                    st.rerun()
                except Exception as error:
                    st.error(f"儲存作答失敗：{error}")

        latest_attempt = quiz.get("latest_attempt")

        if latest_attempt:
            with st.expander("查看最近一次作答"):
                st.write("**你的答案：**")
                st.write(safe_text(latest_attempt.get("user_answer")))
                st.write(
                    "**自評結果：** "
                    f"{safe_text(latest_attempt.get('self_rating_label'))}"
                )
                st.write(
                    "**得分：** "
                    f"{latest_attempt.get('score', 0)} / 2"
                )
                st.caption(
                    "作答時間："
                    f"{format_datetime(latest_attempt.get('answered_at'))}"
                )

        weak_point = quiz.get("weak_point")

        if weak_point:
            status = safe_text(weak_point.get("status"))
            st.caption(
                "目前弱點狀態："
                f"{get_status_label(status)}｜"
                "弱點分數："
                f"{weak_point.get('weakness_score', 0)}"
            )

        st.divider()


def show_wrong_questions(
    document_id: str,
    chapter_id: str | None,
) -> None:
    """顯示錯題本。"""

    wrong_questions = get_wrong_questions(
        document_id=document_id,
        chapter_id=chapter_id,
    )

    if not wrong_questions:
        st.success("目前沒有尚未掌握的錯題。")
        return

    st.metric("錯題數量", len(wrong_questions))

    for index, item in enumerate(wrong_questions, start=1):
        status = safe_text(item.get("status"))
        status_class = get_status_class(status)

        st.markdown(
            (
                '<div class="weak-point-card">'
                '<div class="quiz-question">'
                f'{index}. {safe_text(item.get("question"))}'
                '</div>'
                f'<div class="{status_class}">'
                f'狀態：{get_status_label(status)}'
                '</div></div>'
            ),
            unsafe_allow_html=True,
        )

        info_col1, info_col2, info_col3, info_col4 = st.columns(4)
        info_col1.metric("弱點分數", item.get("weakness_score", 0))
        info_col2.metric("答錯次數", item.get("wrong_count", 0))
        info_col3.metric("部分答對", item.get("partial_count", 0))
        info_col4.metric("答對次數", item.get("correct_count", 0))

        with st.expander("查看答案與解析"):
            st.write("**最近回答：**")
            st.write(safe_text(item.get("last_answer"), "尚無紀錄"))
            st.write("**標準答案：**")
            st.write(safe_text(item.get("correct_answer")))

            explanation = safe_text(item.get("explanation")).strip()
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


def show_weak_points(
    document_id: str,
    chapter_id: str | None,
) -> None:
    """顯示不熟重點。"""

    status_options = {
        "仍然不熟": "active",
        "正在改善": "improving",
        "已掌握": "mastered",
    }

    selected_status_labels = st.multiselect(
        "篩選狀態",
        options=list(status_options.keys()),
        default=["仍然不熟", "正在改善"],
    )

    selected_statuses = [
        status_options[label]
        for label in selected_status_labels
    ]

    weak_points = get_weak_points(
        document_id=document_id,
        chapter_id=chapter_id,
        statuses=selected_statuses,
    )

    if not weak_points:
        st.info("目前沒有符合條件的不熟重點。")
        return

    st.metric("重點數量", len(weak_points))

    for index, item in enumerate(weak_points, start=1):
        status = safe_text(item.get("status"))
        status_class = get_status_class(status)

        st.markdown(
            (
                '<div class="weak-point-card">'
                '<div class="quiz-question">'
                f'{index}. {safe_text(item.get("title"))}'
                '</div>'
                f'<div class="{status_class}">'
                f'狀態：{get_status_label(status)}'
                '</div></div>'
            ),
            unsafe_allow_html=True,
        )

        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("弱點分數", item.get("weakness_score", 0))
        metric_col2.metric(
            "累積失誤",
            item.get("wrong_count", 0) + item.get("partial_count", 0),
        )
        metric_col3.metric("累積答對", item.get("correct_count", 0))

        st.write("**標準答案：**")
        st.write(safe_text(item.get("correct_answer")))

        explanation = safe_text(item.get("explanation")).strip()
        if explanation:
            with st.expander("查看完整解析"):
                st.write(explanation)

        st.caption(
            "章節："
            f"{safe_text(item.get('chapter_title'), '未分類章節')}｜"
            "最後更新："
            f"{format_datetime(item.get('updated_at'))}"
        )
        st.divider()


def show_attempt_history(
    document_id: str,
    chapter_id: str | None,
) -> None:
    """顯示練習紀錄。"""

    limit = st.selectbox(
        "顯示筆數",
        options=[20, 50, 100, 200],
        index=1,
    )

    history = get_quiz_attempt_history(
        document_id=document_id,
        chapter_id=chapter_id,
        limit=limit,
    )

    if not history:
        st.info("目前還沒有 Quiz 練習紀錄。")
        return

    st.metric("紀錄筆數", len(history))

    icon_map = {
        "correct": "✅",
        "partial": "🟡",
        "wrong": "❌",
    }

    for index, item in enumerate(history, start=1):
        rating = safe_text(item.get("self_rating"))
        icon = icon_map.get(rating, "📝")

        with st.expander(
            f"{icon} 第 {index} 筆｜{safe_text(item.get('question'))}"
        ):
            st.write("**你的答案：**")
            st.write(safe_text(item.get("user_answer")))
            st.write("**標準答案：**")
            st.write(safe_text(item.get("correct_answer")))
            st.write(
                "**自評結果：** "
                f"{safe_text(item.get('self_rating_label'))}"
            )
            st.write(f"**得分：** {item.get('score', 0)} / 2")

            explanation = safe_text(item.get("explanation")).strip()
            if explanation:
                st.write("**解析：**")
                st.write(explanation)

            st.caption(
                "章節："
                f"{safe_text(item.get('chapter_title'), '未分類章節')}｜"
                "作答時間："
                f"{format_datetime(item.get('answered_at'))}"
            )


st.title("🧠 Quiz 練習")
st.caption(
    "從已分析文件中進行自評練習，並自動整理錯題與不熟重點。"
)

try:
    documents = get_practice_documents()
except Exception as error:
    st.error(f"讀取練習文件失敗：{error}")
    st.stop()

if not documents:
    st.info(
        "目前沒有可練習的 Quiz。"
        "請先回到主頁生成章節詳細學習筆記，"
        "並確認 Quiz 已寫入 SQLite。"
    )
    st.stop()

document_labels = [
    safe_text(
        document.get("file_name"),
        "未命名文件",
    )
    for document in documents
]

selected_document_index = st.selectbox(
    "選擇文件",
    options=list(range(len(documents))),
    format_func=lambda index: document_labels[index],
    key="quiz_document_selector",
)

selected_document = documents[
    selected_document_index
]

selected_document_id = safe_text(
    selected_document.get("id")
)

try:
    chapters = get_chapters_by_document(selected_document_id)
except Exception as error:
    st.error(f"讀取章節失敗：{error}")
    st.stop()

if not chapters:
    st.info("這份文件目前沒有包含 Quiz 的章節。")
    st.stop()

chapter_labels = [
    (
        f"Module {chapter.get('chapter_order', '?')}｜"
        f"{safe_text(chapter.get('title'), '未命名章節')}｜"
        f"{chapter.get('quiz_count', 0)} 題 Quiz"
    )
    for chapter in chapters
]

selected_chapter_index = st.selectbox(
    "選擇章節",
    options=list(range(len(chapters))),
    format_func=lambda index: chapter_labels[index],
    key=f"quiz_chapter_selector_{selected_document_id}",
)

selected_chapter = chapters[
    selected_chapter_index
]

selected_chapter_id = safe_text(
    selected_chapter.get("id")
)


header_col1, header_col2, header_col3, header_col4 = st.columns(4)
header_col1.metric("文件 Quiz", selected_document.get("quiz_count", 0))
header_col2.metric(
    "文件作答次數",
    selected_document.get("attempt_count", 0),
)
header_col3.metric(
    "未掌握弱點",
    selected_document.get("weak_point_count", 0),
)
header_col4.metric(
    "主章節數",
    selected_document.get("chapter_count", 0),
)

tab_practice, tab_wrong, tab_weak, tab_history = st.tabs(
    ["Quiz 練習", "錯題本", "不熟重點", "練習紀錄"]
)

with tab_practice:
    st.subheader("✍️ Quiz 自評練習")
    try:
        show_quiz_practice(
            document_id=selected_document_id,
            chapter_id=selected_chapter_id,
        )
    except Exception as error:
        st.error(f"載入 Quiz 練習失敗：{error}")

with tab_wrong:
    st.subheader("📕 錯題本")
    wrong_scope = st.radio(
        "錯題範圍",
        options=["目前章節", "整份文件"],
        horizontal=True,
        key="wrong_scope",
    )
    wrong_chapter_id = (
        selected_chapter_id
        if wrong_scope == "目前章節"
        else None
    )
    try:
        show_wrong_questions(
            document_id=selected_document_id,
            chapter_id=wrong_chapter_id,
        )
    except Exception as error:
        st.error(f"載入錯題本失敗：{error}")

with tab_weak:
    st.subheader("📌 不熟重點")
    weak_scope = st.radio(
        "重點範圍",
        options=["目前章節", "整份文件"],
        horizontal=True,
        key="weak_scope",
    )
    weak_chapter_id = (
        selected_chapter_id
        if weak_scope == "目前章節"
        else None
    )
    try:
        show_weak_points(
            document_id=selected_document_id,
            chapter_id=weak_chapter_id,
        )
    except Exception as error:
        st.error(f"載入不熟重點失敗：{error}")

with tab_history:
    st.subheader("🕘 練習紀錄")
    history_scope = st.radio(
        "紀錄範圍",
        options=["目前章節", "整份文件"],
        horizontal=True,
        key="history_scope",
    )
    history_chapter_id = (
        selected_chapter_id
        if history_scope == "目前章節"
        else None
    )
    try:
        show_attempt_history(
            document_id=selected_document_id,
            chapter_id=history_chapter_id,
        )
    except Exception as error:
        st.error(f"載入練習紀錄失敗：{error}")
