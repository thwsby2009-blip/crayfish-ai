# Crayfish AI 小龍蝦 AI

一個結合地圖定位、植物發現記錄與 Gemini AI 的互動式 Web App。

**線上版：** https://thwsby2009-blip.streamlit.app

---

## 功能

- **🌿 全民植物發現地圖** — 記錄你發現的植物位置，並在地图上標示
- **🦞 小龍蝦 AI 助手** — 透過 OpenRouter API 與 AI 對話
- **AI 植物辨識** — 拍攝植物照片，AI 幫你辨識種類
- **位置服務** — 自動抓取目前 GPS 位置，記錄發現地點

---

## 技術架構

- **前端**：Streamlit（Python）
- **資料庫**：Supabase（植物記錄储存）
- **AI 模型**：Google Gemini（AI 辨識）、OpenRouter（對話）
- **依賴管理**：requirements.txt

---

## 檔案結構

- `streamlit_app.py` — 植物發現地圖主程式
- `main.py` — 小龍蝦 AI 助手
- `requirements.txt` — Python 依賴

---

## 本地運行

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
# 或
streamlit run main.py
```

---

## 需要的 API Key

- **Supabase Key** — 設定於 Streamlit Secrets
- **Gemini API Key** — https://aistudio.google.com/apikey（免費申請）
- **OpenRouter API Key** — 用於 AI 對話功能