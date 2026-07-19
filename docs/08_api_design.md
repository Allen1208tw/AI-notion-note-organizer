# 外部 API 與內部 Service 介面

## API 邊界

目前沒有公開 REST API。Streamlit UI 直接呼叫 Python Service。外部 API 是 OpenAI 與 Notion；內部 API 是 Service 對頁面提供的函式。

## OpenAI

`openai_service.py` 集中建立 Client，Key 只由 `.env` 讀取。主要任務包括 Chunk 分析、整體合併、詳細章節、PDF 視覺分析及品質修復。

外部回應一律視為不可信輸入，需要處理空回應、非 JSON、型別錯誤、限流、網路錯誤與暫時失敗。

## Notion

`notion_service.py` 提供通用操作；`chapter_notion_service.py` 處理父頁、章節子頁、Block 排版、圖片上傳、快取與續跑。Token 和父頁 ID 由環境設定提供。

Notion Builder 接收已驗證的 `ChapterLearningNote`，建立 Callout、Heading、Toggle、Code、Table 和 Image。長內容需切分 Rich Text，父子 Block 必須符合 API 結構。

## 匯出結果契約

典型結果包含父頁資訊、完成與失敗章節、本次處理數、快取命中數和 `is_finished`。歷史版本的章節可能是字串、整數或 dict，所以邊界會 normalize，再計算完成、失敗和等待數。

## 內部 Service 原則

- Page 傳 ID 和表單值，不傳 SQLAlchemy Session。
- Service 自己管理 Session、驗證與交易。
- 寫入回傳新增、跳過、總數和失敗原因。
- 可恢復情況用結構化結果，真正例外才拋給 UI。
- UI 不直接呼叫 OpenAI、Notion 或拼 SQL。

## 重要介面

文件與內容：`create_or_update_document()`、`save_chapter_learning_items()`、統計和刪除函式。

Quiz：取得文件/章節/題目、`save_quiz_attempt()`、弱點與歷史查詢。

Flash Card：取得卡片、儲存熟悉度、更新排程、查詢摘要和紀錄。

維護：文件診斷、章節/文件清理、單章或整份快取同步、重複資料合併。

背景工作：`create_background_job()` 建立工作，Worker 以 `claim_next_background_job()` 領取，透過 `update_background_job_progress()` 回報進度，完成後以 `save_background_job_result()` 儲存可恢復結果。Page 不直接啟動執行緒，也不把長時間工作綁在 Streamlit rerun 上。

更新：`check_for_updates()` 讀取內建 Repository 的 GitHub latest Release，`download_update()` 串流下載並驗證 Release Asset digest，`launch_update_installer()` 只執行已驗證的 Windows 安裝檔。使用者不需提供更新網址或 Manifest。

## 冪等性

Notion 依匯出狀態避免重複建頁；SQLite 依 identity merge 達到近似冪等。同一快取同步兩次，第二次應跳過，不應增加相同題目。

## 交易邊界

一次 Quiz 作答會同時新增 Attempt 和更新 WeakPoint，兩者在同一 SQL 交易完成。任何一步失敗都 rollback。

Notion 與 SQLite 無法共享交易，因此採用快取與狀態檔支援重試的最終一致性策略，而不是假裝兩個外部系統能原子提交。

## 重試

AI 與 Notion 的重試都應有限次數並保留原始錯誤。Notion 章節級續跑比整份重做更省時，也降低重複頁面風險。

## 未來公開 API

多人版可在 Service 外加 FastAPI，例如文件上傳、分析 Job、Notion 匯出、Quiz Attempt、Flashcard Review 和 Dashboard Endpoint。屆時需新增登入、`user_id`、權限、背景 Job、物件儲存和 API 版本控制。
