# 核心程式碼導讀

## 如何沿著功能讀 Code

遵循「Page -> Service -> Model/External API」即可。Page 告訴你使用者做什麼，Service 告訴你業務規則，Model 告訴你資料如何持久化。

## 應用啟動

```text
啟動_AI筆記整理器.bat
-> .venv\Scripts\python.exe launcher.py
-> 檢查依賴與 SQLite Schema
-> 選擇 localhost Port
-> python -m streamlit run AI_Notion_筆記整理器.py
-> 開啟瀏覽器
```

如果雙擊無反應，先從終端執行 `.bat` 或 `launcher.py` 取得錯誤；常見原因是虛擬環境不存在、依賴缺少、入口檔名不符或 Port/狀態檔異常。

## 文件上傳到分析

主入口先驗證檔案，再依副檔名呼叫 Parser。文字經 `clean_text()` 與 `chunk_text()` 後，`analyze_document()` 逐塊分析並合併。結果保存在 Session State 供同一頁顯示和匯出。

同時，`detect_chapters()` 從完整文字找主章節。它的結果不只是 UI 標題，也會成為 SQLite `source_chapter_id`、快取定位和 Notion 子頁名稱，所以這個模組的錯誤會沿整條資料流放大。

## 文件寫入 SQLite

主頁呼叫 `create_or_update_document()`。函式先用檔案 Hash 找既有 Document，再建立新舊章節 map。配對成功的章節沿用 ID並更新標題/索引；新增章節建立 UUID；消失章節才清理。

這段 code 的核心不是 Insert，而是「重新分析時如何保留歷史」。

## 詳細筆記生成

Notion 流程逐章執行：

```text
load visual cache
-> miss 時 analyze PDF pages
-> load note cache
-> miss 時 analyze_chapter
-> validate ChapterLearningNote
-> save note cache
-> build Notion blocks
-> create child page
-> record export state
-> merge Quiz/Flashcard into SQLite
```

任何步驟失敗都應留下足夠狀態，使下一次能從該章繼續。

## Notion Block Builder

`chapter_notion_service.py` 讀取 `ChapterLearningNote` 各欄位，依固定順序建立摘要 Callout、白話講解、學習目標 Toggle、學習地圖、彩色重點、術語、規則、比較表、程式碼 Toggle、錯誤 Callout、子章節、圖片、練習建議、Quiz Toggle 和 Flash Card Toggle。

Quiz/Flash Card 的摺疊不是 AI 產生的 Markdown，而是 Python 建立 Notion 原生 Toggle Block，因此格式穩定且可互動。

## 題目同步與去重

`save_chapter_learning_items()` 從 Pydantic 物件讀 Quiz/Flash Card。先略過空白，再用 `learning_item_identity.py` 正規化空白、大小寫與標點，與該章既有 identity 比對，只新增缺少內容。

函式回傳總數、新增數與跳過數。UI 因此能區分「同步成功但全部已存在」和「真的失敗」。

## Quiz 作答

`pages/2_quiz練習.py` 只處理選擇、輸入和顯示。`quiz_practice_service.save_quiz_attempt()` 驗證自評、轉換分數、建立 Attempt，再更新 WeakPoint。

WeakPoint 是 Quiz 歷次表現的摘要，不取代 Attempt 歷史。Attempt 用來回答「每次答了什麼」；WeakPoint 用來回答「目前哪題最弱」。

## Flash Card 評分

`pages/3_flash_card複習.py` 維護目前索引與翻面狀態。Service 新增 Review，並依評分更新 `ReviewSchedule`。低分縮短間隔並重設重複次數，高分逐步延長間隔。

即使 UI 暫時不顯示「今日到期」，排程資料仍保留，未來可重新開啟該功能。

## 儀表板計算

`learning_dashboard_service.py` 聚合：Quiz 作答分布與分數、不同卡片的最近熟悉度、到期排程、未掌握 WeakPoint 和近期活動。

答對率是 `correct / attempts`；Quiz 得分率考慮部分答對；Flash Card 完成率是曾複習的不同卡片數除以卡片總數。這三者不能互換。

## 管理與修復

`learning_data_admin_service.py` 提供診斷、刪除和去重。合併重複題目時，需要把 Attempt、WeakPoint 或 Review/Schedule 關聯轉到保留項目後，再刪重複資料，否則會遺失歷史。

單章快取同步走 `chapter_notion_service.sync_single_chapter_cache_to_sqlite()`，只讀快取和寫 SQLite，不呼叫 AI、不建立 Notion。

## 常見修改應去哪裡

| 需求 | 主要修改位置 |
|---|---|
| 新增支援檔案格式 | `src/parsers/`、validator、主入口分派 |
| 改章節標題規則 | `chapter_detector.py` 與其測試 |
| 新增 AI 輸出欄位 | Prompt + Pydantic Model + Renderers |
| 改 Notion 排版 | `chapter_notion_service.py` |
| 改 Quiz 分數 | `quiz_practice_service.py`、儀表板、文件 |
| 改 Flash Card 排程 | `flashcard_practice_service.py` |
| 新增資料欄位 | Model + Migration/Schema 檢查 + Service |
| 改頁面互動 | 對應 `pages/`，資料規則仍留在 Service |

## 一項待清理技術債

`src/processors/learning_database.py` 並非現行主要 Database Service。新程式應 import `src/services/learning_database_service.py`。移除前先用 `rg` 確認沒有舊引用，再以測試驗證。
