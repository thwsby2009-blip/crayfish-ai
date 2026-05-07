import streamlit as st
from supabase import create_client, Client
import time
import google.generativeai as genai
import pandas as pd

# ====================== 1. 設定與初始化 ======================
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
GEMINI_API_KEY = st.secrets.get("GEMINI_KEY")

if not GEMINI_API_KEY or not SUPABASE_KEY:
    st.error("❌ 金鑰讀取失敗")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# ====================== 2. 介面中文化黑科技 (CSS) ======================
st.set_page_config(page_title="植物地圖", layout="centered", page_icon="🌿")

# 這段 CSS 會強制改掉鏡頭開啟後的 "Take Photo" 按鈕文字
st.markdown(
    """
    <style>
    /* 隱藏原本的 "Take Photo" 文字 */
    div[data-testid="stCameraInputButton"] button p {
        display: none !important;
    }
    /* 插入中文文字 */
    div[data-testid="stCameraInputButton"] button::after {
        content: "📸 立即拍照";
        font-weight: bold;
    }
    /* 順便優化上傳按鈕樣式 */
    .stButton button {
        width: 100%;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🌿 全民植物發現地圖")

# ====================== 3. 照片輸入區 ======================
img_file = st.camera_input("請對準植物並按下下方按鈕")

# 如果沒拍照，提供上傳選項
if not img_file:
    img_file = st.file_uploader("或者從相簿選擇", type=["jpg", "jpeg", "png"])

# ====================== 4. 主要邏輯 ======================
if img_file is not None:
    st.image(img_file, width=300)
    
    img_id = f"{img_file.name}_{img_file.size}"
    
    if "ai_cache" not in st.session_state or st.session_state.get("last_img_id") != img_id:
        with st.spinner("🤖 AI 正在辨識中..."):
            try:
                # 這裡改回你環境中唯一可用的 2.5 版本 (名稱請依你測試成功的填寫)
                model = genai.GenerativeModel('gemini-2.0-flash-lite-preview-02-05') 
                
                prompt = "請辨識此植物。格式：\n中文名稱：xxx\n學名：xxx\n科別：xxx\n簡介：xxx（50字內）"
                
                response = model.generate_content([
                    prompt,
                    {"mime_type": "image/jpeg", "data": img_file.getvalue()}
                ])
                st.session_state.ai_cache = response.text
                st.session_state.last_img_id = img_id
            except Exception as e:
                st.error(f"辨識錯誤：{e}")
                st.session_state.ai_cache = "辨識失敗"

    ai_result = st.session_state.ai_cache
    st.info(f"💡 辨識結果：\n{ai_result}")

    # 提取名稱
    default_name = ""
    if "中文名稱：" in ai_result:
        default_name = ai_result.split("中文名稱：")[1].split("\n")[0].strip()

    plant_name = st.text_input("確認植物名稱", value=default_name)

    if st.button("🚀 確認並發布到地圖", type="primary"):
        try:
            with st.spinner("存檔中..."):
                ts = int(time.time())
                file_path = f"public/plant_{ts}.jpg"
                
                # 上傳 Storage
                supabase.storage.from_("plant-images").upload(
                    path=file_path,
                    file=img_file.getvalue(),
                    file_options={"content-type": "image/jpeg"}
                )
                img_url = supabase.storage.from_("plant-images").get_public_url(file_path)

                # 寫入資料庫
                supabase.table("plants").insert({
                    "name": plant_name,
                    "image_url": img_url,
                    "latitude": 25.0330,
                    "longitude": 121.5654,
                    "ai_result": ai_result
                }).execute()

                st.balloons()
                st.success("成功發布！")
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"失敗：{e}")

# ====================== 5. 地圖顯示 ======================
st.divider()
try:
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    if res.data:
        df = pd.DataFrame(res.data).rename(columns={"latitude": "lat", "longitude": "lon"})
        st.map(df)
except:
    pass
