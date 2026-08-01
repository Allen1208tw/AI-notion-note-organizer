# AI Notion 筆記整理器 v3.2.7

這個版本集中修正 Notion 連線、背景匯出、Gemini 額度錯誤與 Windows 安裝體驗，並首次提供不需要另外安裝 Python 的一鍵安裝程式。

## 主要更新

- 新增 Windows 一鍵安裝檔，內含 Python 執行環境與所有必要套件。
- 安裝後可由桌面或開始功能表啟動，不再顯示黑色命令列視窗。
- 啟動與背景程序的診斷訊息會寫入：
  `%LOCALAPPDATA%\AI Notion Note Organizer\logs\launcher.log`
- 啟動檢查失敗時會顯示 Windows 錯誤視窗，並指出日誌位置。

## Notion 修正

- 支援完整 Notion 頁面網址與 32 位 Page ID，包括：
  `https://app.notion.com/p/頁面名稱-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- 儲存設定與連線前會驗證 Notion Integration Token，避免把中文提示文字或錯誤內容誤當 Token 傳送。
- 修正舊環境變數蓋過最新 `.env` 設定的問題，重新儲存後可立即使用新 Token 與父頁 ID。
- 背景匯出未完成時不再誤報成功；會顯示已完成 Module 數量及第一個實際錯誤，方便修正後續跑。
- 已完成與失敗狀態的整理更穩定，降低父頁建立成功、子頁卻沒有內容時難以追查的情況。

## Gemini 額度處理

- Gemini 回傳 `429 RESOURCE_EXHAUSTED` 時，系統會停止繼續消耗後續 Module 請求。
- 錯誤訊息會明確提示等待額度重置，或切換至其他 AI 供應商後再續跑。
- 此錯誤代表 Google Gemini 專案或模型額度已用盡，不是 Notion 連線問題。

## 安裝方式

1. 下載 `AI_Notion_Note_Organizer_Setup.exe`。
2. 雙擊安裝，依畫面完成步驟。
3. 安裝完成後可直接啟動程式。
4. 第一次使用請在「開始使用與設定」頁填入自己的 API Key、Notion Token 與父頁網址。

安裝程式不包含任何開發者或使用者的 API Key、`.env`、資料庫、輸出文件與背景工作內容。

## 從舊版升級

- 可直接執行新版安裝程式覆蓋舊版。
- 個人設定、SQLite 學習資料、輸出內容與背景工作狀態會保留在：
  `%LOCALAPPDATA%\AI Notion Note Organizer`
- 解除安裝程式本體時，個人資料預設不會被刪除。

## Windows SmartScreen 提示

此安裝檔目前尚未購買程式碼簽章憑證，因此 Windows 可能顯示「Windows 已保護您的電腦」或「未知的發行者」。請先核對下方 SHA-256；確認檔案來源與雜湊正確後，可選擇「其他資訊」→「仍要執行」。

## 檔案資訊

- 檔名：`AI_Notion_Note_Organizer_Setup.exe`
- 大小：88.28 MB（92,567,711 bytes）
- SHA-256：`9E0B403DCBE8AE0B29500A6A154E243A7DCBC4AD9BB72E8ABF182D84400EBB79`

## 驗證結果

- 自動化測試：42 項通過
- 凍結版環境與 SQLite Schema 檢查：通過
- Windows GUI subsystem：2（不顯示命令列視窗）
- 敏感資料發行稽核：通過
- 靜默安裝與解除安裝測試：通過
