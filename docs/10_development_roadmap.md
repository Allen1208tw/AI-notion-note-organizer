# 開發路線與版本演進

## V1：文件分析 MVP

完成多格式解析、文字清理、Chunk、OpenAI 分析、摘要、Mermaid、Quiz、Flash Card、Markdown/JSON 與基本 Notion 匯出。目標是證明「文件能轉成學習內容」。

## V1.5：詳細章節學習筆記

加入主章節偵測、描述性標題、逐章詳細筆記、PDF 視覺分析、比較表、程式碼範例、Callout、Quiz/Flash Card Toggle，以及 Notion 父頁與章節子頁。

## V1.6：快取與可恢復匯出

將視覺分析與詳細筆記分層快取；建立 Notion 匯出狀態，支援失敗續跑；補上舊快取 fallback 和快取回填 SQLite。

## V2.1：統一資料庫 Schema

統一 UUID、Document/Chapter 欄位、ReviewSchedule 多型 ID、QuizAttempt 三段自評，新增 WeakPoint，處理舊 SQLite Schema 不會自動升級的問題。

## V2.2：Quiz 練習

建立作答、自評、歷史、錯題本與 WeakPoint 更新。重點不是顯示題目，而是把每次作答持久化並建立弱點模型。

## V2.3：Flash Card 練習

建立章節翻卡、0 到 5 熟悉度、Review 歷史與簡化間隔排程。依使用需求簡化 UI，保留後端排程擴充能力。

## V2.4：學習儀表板

整合 Quiz、Flash Card、弱點、到期排程與近期活動，建立學習健康分數和優先複習指標。

## V2.5：穩定性與體驗

完成資料診斷、單章快取同步、重複項目合併、非破壞性重新分析、章節偵測修復、中文頁面、一鍵啟動與備份流程。這一版將「能跑」提升到「能維護和修復」。

## V2.6：技術統整

目前階段。補齊架構、Schema、資料流、Prompt、API、UI、Code Walkthrough、展示與問答，讓專案可以交接、展示和繼續擴充。

## V3：Windows 發行版與背景工作

已完成 SQLite 持久化背景工作佇列、獨立 Worker、進度與取消、中斷恢復、PyInstaller 封裝、Inno Setup 單一安裝 EXE、AppData 資料隔離，以及 GitHub Releases + SHA-256 零設定更新流程。

後續發行改善可加入程式碼簽章、正式下載主機、CI 自動建置與 Delta Update。目前採完整安裝程式覆蓋應用程式檔案，個人資料因位於 AppData 而不受影響。

建議項目：AppData 持久資料目錄、正式 Migration、日誌、版本號、圖示、PyInstaller/安裝程式、更新與解除安裝。先確保 SQLite 和快取不寫進 EXE 臨時目錄。

## V4：雲端多人版

需要新增帳號、`user_id` 資料隔離、PostgreSQL、物件儲存、背景工作、Secret 管理、API 層、監控與權限。不是把現有 Streamlit 直接部署就完成。

## 優先技術債

1. 導入 Alembic，取代只檢查不遷移的 Schema 策略。
2. 移除或正式標記 `src/processors/learning_database.py` 舊檔。
3. 為 Chapter Detector 建立更多真實教材 fixture。
4. 為 Notion Block Builder 加入 payload 單元測試。
5. 將長任務抽成 Job 狀態，降低 Streamlit rerun 風險。
6. 統一所有 Service 的回傳 DTO，減少 dict 格式演進問題。

## 衡量完成的標準

版本完成不只看頁面出現，而要確認：重開後資料仍在、同一操作重跑不重複、部分失敗可恢復、歷史不被重建流程刪除、錯誤可診斷、文件和測試與實作一致。
