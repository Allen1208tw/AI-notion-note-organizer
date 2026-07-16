from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.services.flashcard_practice_service import (
    get_flashcard_chapters,
    get_flashcard_documents,
    get_flashcard_review_history,
    get_flashcard_summary,
    get_flashcards_by_chapter,
    save_flashcard_review,
)


st.set_page_config(
    page_title="Flash Card 複習",
    page_icon="🗂️",
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

        .flashcard-shell {
            border: 1px solid rgba(128, 128, 128, 0.28);
            border-radius: 18px;
            padding: 24px;
            margin: 10px 0 18px 0;
            background: rgba(127, 127, 127, 0.05);
            min-height: 220px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .flashcard-label {
            font-size: 0.9rem;
            opacity: 0.65;
            margin-bottom: 12px;
        }

        .flashcard-content {
            font-size: 1.35rem;
            line-height: 1.75;
            font-weight: 700;
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        .flashcard-back {
            font-size: 1.15rem;
            line-height: 1.75;
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        .review-card {
            border: 1px solid rgba(128, 128, 128, 0.22);
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 12px;
            background: rgba(127, 127, 127, 0.035);
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


def format_datetime(value) -> str:
    """格式化日期時間。"""

    if value is None:
        return "尚未安排"

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    return safe_text(value, "未知時間")


def build_document_options(
    documents: list[dict],
) -> dict[str, str]:
    """建立不顯示 ID 的文件選項。"""

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

        if label in options:
            label = f"{label}｜{safe_text(document.get('id'))[:8]}"

        options[label] = safe_text(
            document.get("id")
        )

    return options


def build_chapter_options(
    chapters: list[dict],
) -> dict[str, str]:
    """建立章節選項。"""

    options: dict[str, str] = {}

    for chapter in chapters:
        order = chapter.get(
            "chapter_order",
            "?",
        )

        title = safe_text(
            chapter.get("title"),
            "未命名章節",
        )

        flashcard_count = chapter.get(
            "flashcard_count",
            0,
        )

        label = (
            f"Module {order}｜{title}｜"
            f"{flashcard_count} 張 Flash Cards"
        )

        options[label] = safe_text(
            chapter.get("id")
        )

    return options


def get_familiarity_label(score: int) -> str:
    """取得熟悉度文字。"""

    labels = {
        0: "完全不熟",
        1: "很不熟",
        2: "有點不熟",
        3: "普通",
        4: "熟悉",
        5: "非常熟悉",
    }

    return labels.get(
        score,
        str(score),
    )


def initialize_review_state(
    flashcards: list[dict],
    state_prefix: str,
) -> None:
    """初始化指定複習區域的狀態。"""

    ids_key = f"{state_prefix}_ids"
    index_key = f"{state_prefix}_index"
    show_back_key = f"{state_prefix}_show_back"

    flashcard_ids = [
        safe_text(
            item.get("id")
        )
        for item in flashcards
    ]

    current_ids = st.session_state.get(
        ids_key,
        [],
    )

    if current_ids != flashcard_ids:
        current_index = st.session_state.get(
            index_key,
            0,
        )

        st.session_state[
            ids_key
        ] = flashcard_ids

        if current_index >= len(flashcard_ids):
            current_index = 0

        st.session_state[
            index_key
        ] = current_index

        st.session_state[
            show_back_key
        ] = False


def clear_review_state(
    state_prefix: str,
) -> None:
    """清除指定複習區域的狀態。"""

    for suffix in [
        "ids",
        "index",
        "show_back",
    ]:
        st.session_state.pop(
            f"{state_prefix}_{suffix}",
            None,
        )


def show_summary_metrics(
    document_id: str,
    chapter_id: str | None = None,
) -> None:
    """顯示 Flash Card 複習統計。"""

    summary = get_flashcard_summary(
        document_id=document_id,
        chapter_id=chapter_id,
    )

    row1_col1, row1_col2, row1_col3, row1_col4 = (
        st.columns(4)
    )

    row1_col1.metric(
        "Flash Cards",
        summary.get(
            "flashcard_count",
            0,
        ),
    )

    row1_col2.metric(
        "已複習卡片",
        summary.get(
            "reviewed_flashcard_count",
            0,
        ),
    )

    row1_col3.metric(
        "尚未複習",
        summary.get(
            "unreviewed_count",
            0,
        ),
    )

    row1_col4.metric(
        "今日到期",
        summary.get(
            "due_count",
            0,
        ),
    )

    row2_col1, row2_col2 = st.columns(2)

    row2_col1.metric(
        "累積複習次數",
        summary.get(
            "review_count",
            0,
        ),
    )

    row2_col2.metric(
        "平均熟悉度",
        (
            f"{summary.get('average_familiarity_score', 0)}"
            " / 5"
        ),
    )


def show_flashcard_review(
    document_id: str,
    chapter_id: str,
    due_only: bool,
    state_prefix: str,
) -> None:
    """顯示單張 Flash Card 複習流程。"""

    flashcards = get_flashcards_by_chapter(
        document_id=document_id,
        chapter_id=chapter_id,
        due_only=due_only,
    )

    if not flashcards:
        if due_only:
            st.success(
                "目前沒有到期需要複習的 Flash Card。"
            )
        else:
            st.info(
                "這個章節目前沒有 Flash Card。"
            )

        clear_review_state(
            state_prefix
        )
        return

    initialize_review_state(
        flashcards=flashcards,
        state_prefix=state_prefix,
    )

    ids_key = f"{state_prefix}_ids"
    index_key = f"{state_prefix}_index"
    show_back_key = f"{state_prefix}_show_back"

    flashcard_map = {
        safe_text(item.get("id")): item
        for item in flashcards
    }

    review_ids = st.session_state.get(
        ids_key,
        [],
    )

    if not review_ids:
        st.info(
            "目前沒有可複習的 Flash Card。"
        )
        return

    current_index = st.session_state.get(
        index_key,
        0,
    )

    if current_index >= len(review_ids):
        st.success(
            "這一輪 Flash Card 已全部複習完成。"
        )

        if st.button(
            "重新開始這一輪",
            key=f"{state_prefix}_restart",
            type="primary",
        ):
            st.session_state[
                index_key
            ] = 0

            st.session_state[
                show_back_key
            ] = False

            st.rerun()

        return

    current_id = review_ids[
        current_index
    ]

    current_card = flashcard_map.get(
        current_id
    )

    if current_card is None:
        st.session_state[
            index_key
        ] = current_index + 1

        st.rerun()

    progress_value = (
        current_index + 1
    ) / len(review_ids)

    st.progress(
        progress_value,
        text=(
            f"第 {current_index + 1} / "
            f"{len(review_ids)} 張"
        ),
    )

    st.markdown(
        (
            '<div class="flashcard-shell">'
            '<div class="flashcard-label">'
            '正面'
            '</div>'
            '<div class="flashcard-content">'
            f'{safe_text(current_card.get("front"))}'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

    schedule = current_card.get(
        "schedule"
    )

    latest_review = current_card.get(
        "latest_review"
    )

    info_col1, info_col2 = st.columns(2)

    with info_col1:
        if latest_review:
            st.caption(
                "上次熟悉度："
                f"{safe_text(latest_review.get('familiarity_label'))}"
            )
        else:
            st.caption(
                "這張卡尚未複習過。"
            )

    with info_col2:
        if schedule:
            st.caption(
                "目前排程："
                f"{format_datetime(schedule.get('due_at'))}"
            )
        else:
            st.caption(
                "尚未建立複習排程。"
            )

    if not st.session_state.get(
        show_back_key,
        False,
    ):
        if st.button(
            "翻面查看答案",
            key=f"{state_prefix}_reveal_{current_id}",
            type="primary",
            width="stretch",
        ):
            st.session_state[
                show_back_key
            ] = True

            st.rerun()

        return

    st.markdown(
        (
            '<div class="flashcard-shell">'
            '<div class="flashcard-label">'
            '背面'
            '</div>'
            '<div class="flashcard-back">'
            f'{safe_text(current_card.get("back"))}'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

    st.markdown("#### 請評估你的熟悉度")

    row1_col1, row1_col2, row1_col3 = (
        st.columns(3)
    )

    row2_col1, row2_col2, row2_col3 = (
        st.columns(3)
    )

    score_clicked = None

    with row1_col1:
        if st.button(
            "0｜完全不熟",
            key=(
                f"{state_prefix}_score_0_"
                f"{current_id}"
            ),
            width="stretch",
        ):
            score_clicked = 0

    with row1_col2:
        if st.button(
            "1｜很不熟",
            key=(
                f"{state_prefix}_score_1_"
                f"{current_id}"
            ),
            width="stretch",
        ):
            score_clicked = 1

    with row1_col3:
        if st.button(
            "2｜有點不熟",
            key=(
                f"{state_prefix}_score_2_"
                f"{current_id}"
            ),
            width="stretch",
        ):
            score_clicked = 2

    with row2_col1:
        if st.button(
            "3｜普通",
            key=(
                f"{state_prefix}_score_3_"
                f"{current_id}"
            ),
            width="stretch",
        ):
            score_clicked = 3

    with row2_col2:
        if st.button(
            "4｜熟悉",
            key=(
                f"{state_prefix}_score_4_"
                f"{current_id}"
            ),
            width="stretch",
        ):
            score_clicked = 4

    with row2_col3:
        if st.button(
            "5｜非常熟悉",
            key=(
                f"{state_prefix}_score_5_"
                f"{current_id}"
            ),
            width="stretch",
            type="primary",
        ):
            score_clicked = 5

    if score_clicked is not None:
        try:
            result = save_flashcard_review(
                flashcard_id=current_id,
                familiarity_score=score_clicked,
            )

            schedule_result = result.get(
                "schedule",
                {},
            )

            st.success(
                "複習紀錄已儲存。"
                f"下次複習："
                f"{format_datetime(schedule_result.get('due_at'))}"
            )

            st.session_state[
                index_key
            ] = current_index + 1

            st.session_state[
                show_back_key
            ] = False

            st.rerun()

        except Exception as error:
            st.error(
                f"儲存複習結果失敗：{error}"
            )


def show_all_flashcards(
    document_id: str,
    chapter_id: str,
) -> None:
    """顯示章節全部 Flash Cards。"""

    flashcards = get_flashcards_by_chapter(
        document_id=document_id,
        chapter_id=chapter_id,
        due_only=False,
    )

    if not flashcards:
        st.info(
            "這個章節目前沒有 Flash Cards。"
        )
        return

    st.metric(
        "卡片數量",
        len(flashcards),
    )

    for index, card in enumerate(
        flashcards,
        start=1,
    ):
        with st.expander(
            (
                f"Flash Card {index}｜"
                f"{safe_text(card.get('front'))}"
            )
        ):
            st.write("**正面：**")
            st.write(
                safe_text(
                    card.get("front")
                )
            )

            st.write("**背面：**")
            st.write(
                safe_text(
                    card.get("back")
                )
            )

            latest_review = card.get(
                "latest_review"
            )

            schedule = card.get(
                "schedule"
            )

            if latest_review:
                st.write(
                    "**最近熟悉度：** "
                    f"{safe_text(latest_review.get('familiarity_label'))}"
                )

                st.caption(
                    "最近複習："
                    f"{format_datetime(latest_review.get('reviewed_at'))}"
                )
            else:
                st.info(
                    "尚未複習這張卡。"
                )

            if schedule:
                st.caption(
                    "下次複習："
                    f"{format_datetime(schedule.get('due_at'))}｜"
                    "間隔："
                    f"{schedule.get('interval_days', 1)} 天"
                )


def show_review_history(
    document_id: str,
    chapter_id: str | None,
) -> None:
    """顯示 Flash Card 複習紀錄。"""

    limit = st.selectbox(
        "顯示筆數",
        options=[
            20,
            50,
            100,
            200,
        ],
        index=1,
        key="flashcard_history_limit",
    )

    history = get_flashcard_review_history(
        document_id=document_id,
        chapter_id=chapter_id,
        limit=limit,
    )

    if not history:
        st.info(
            "目前還沒有 Flash Card 複習紀錄。"
        )
        return

    st.metric(
        "紀錄筆數",
        len(history),
    )

    for index, item in enumerate(
        history,
        start=1,
    ):
        with st.expander(
            (
                f"第 {index} 筆｜"
                f"{safe_text(item.get('front'))}"
            )
        ):
            st.write("**正面：**")
            st.write(
                safe_text(
                    item.get("front")
                )
            )

            st.write("**背面：**")
            st.write(
                safe_text(
                    item.get("back")
                )
            )

            st.write(
                "**熟悉度：** "
                f"{safe_text(item.get('familiarity_label'))}"
                f"（{item.get('familiarity_score', 0)} / 5）"
            )

            st.caption(
                "章節："
                f"{safe_text(item.get('chapter_title'), '未分類章節')}｜"
                "複習時間："
                f"{format_datetime(item.get('reviewed_at'))}"
            )


st.title("🗂️ Flash Card 複習")
st.caption(
    "依照文件與章節進行 Flash Card 翻卡練習，"
    "並記錄每張卡片的熟悉度。"
)

try:
    documents = get_flashcard_documents()
except Exception as error:
    st.error(
        f"讀取 Flash Card 文件失敗：{error}"
    )
    st.stop()

if not documents:
    st.info(
        "目前沒有可複習的 Flash Cards。"
        "請先回到主頁生成章節詳細學習筆記，"
        "並確認 Flash Cards 已寫入 SQLite。"
    )
    st.stop()

document_labels = list(build_document_options(documents).keys())

selected_document_index = st.selectbox(
    "選擇文件",
    options=list(range(len(documents))),
    format_func=lambda index: document_labels[index],
    key="flashcard_document_selector",
)

selected_document = documents[
    selected_document_index
]

selected_document_id = safe_text(
    selected_document.get("id")
)

try:
    chapters = get_flashcard_chapters(
        selected_document_id
    )
except Exception as error:
    st.error(
        f"讀取章節失敗：{error}"
    )
    st.stop()

if not chapters:
    st.info(
        "這份文件目前沒有包含 Flash Cards 的章節。"
    )
    st.stop()

chapter_labels = [
    (
        f"Module {chapter.get('chapter_order', '?')}｜"
        f"{safe_text(chapter.get('title'), '未命名章節')}｜"
        f"{chapter.get('flashcard_count', 0)} 張 Flash Cards"
    )
    for chapter in chapters
]

selected_chapter_index = st.selectbox(
    "選擇章節",
    options=list(range(len(chapters))),
    format_func=lambda index: chapter_labels[index],
    key=f"flashcard_chapter_selector_{selected_document_id}",
)

selected_chapter = chapters[
    selected_chapter_index
]

selected_chapter_id = safe_text(
    selected_chapter.get("id")
)


header_col1, header_col2, header_col3, header_col4 = (
    st.columns(4)
)

header_col1.metric(
    "文件 Flash Cards",
    selected_document.get(
        "flashcard_count",
        0,
    ),
)

header_col2.metric(
    "累積複習次數",
    selected_document.get(
        "review_count",
        0,
    ),
)

header_col3.metric(
    "本章卡片數",
    next(
        (
            chapter.get(
                "flashcard_count",
                0,
            )
            for chapter in chapters
            if safe_text(
                chapter.get("id")
            )
            == selected_chapter_id
        ),
        0,
    ),
)

header_col4.metric(
    "主章節數",
    selected_document.get(
        "chapter_count",
        0,
    ),
)

tab_practice, tab_list, tab_history = st.tabs(
    [
        "章節練習",
        "卡片總覽",
        "複習紀錄",
    ]
)

with tab_practice:
    st.subheader("🔁 章節練習")

    show_summary_metrics(
        document_id=selected_document_id,
        chapter_id=selected_chapter_id,
    )

    try:
        show_flashcard_review(
            document_id=selected_document_id,
            chapter_id=selected_chapter_id,
            due_only=False,
            state_prefix="flashcard_chapter_review",
        )
    except Exception as error:
        st.error(
            f"載入章節 Flash Card 練習失敗：{error}"
        )

with tab_list:
    st.subheader("📚 卡片總覽")

    try:
        show_all_flashcards(
            document_id=selected_document_id,
            chapter_id=selected_chapter_id,
        )
    except Exception as error:
        st.error(
            f"載入卡片總覽失敗：{error}"
        )

with tab_history:
    st.subheader("🕘 複習紀錄")

    history_scope = st.radio(
        "紀錄範圍",
        options=[
            "目前章節",
            "整份文件",
        ],
        horizontal=True,
        key="flashcard_history_scope",
    )

    history_chapter_id = (
        selected_chapter_id
        if history_scope == "目前章節"
        else None
    )

    try:
        show_review_history(
            document_id=selected_document_id,
            chapter_id=history_chapter_id,
        )
    except Exception as error:
        st.error(
            f"載入複習紀錄失敗：{error}"
        )
