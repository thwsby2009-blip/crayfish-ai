import streamlit as st
from supabase import create_client, Client
import time
import google.generativeai as genai
import pandas as pd
from streamlit_js_eval import streamlit_js_eval, get_geolocation

# ====================== 1. 設定區 ======================
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
GEMINI_API_KEY = st.secrets.get("GEMINI_KEY")

genai.configure(api_key=GEMINI_API_KEY)

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# ====================== 2. 頁面佈局與中文化 CSS ======================
st.set_page_config(page_title="植物發現地圖", layout="centered", page_icon="🌿")

st.markdown("""
    <style>
    button[data-testid="stCameraInputButton"] { font-size: 0px !important; }
    button[data-testid="stCameraInputButton"]::after { content: "📸 點此拍照"; font-size: 16px !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🌿 全民植物發現地圖")

# ====================== 3. 定位功能 (Google 樣式定位鈕) ======================
st.subheader("📍 第一步：確認你的位置")
col_gps, col_show = st.columns([1, 1])

# 初始化 session state 座標（預設台北 101）
if "lat" not in st.session_state:
    st.session_state.lat = 25.0330
    st.session_state.lon = 121.5654

with col_gps:
    if st.button("🎯 點我取得目前精確定位"):
        # 使用 javascript 獲取定位
        loc = get_geolocation()
        if loc:
            st.session_state.lat = loc['coords']['latitude']
            st.session_state.lon = loc['coords']['longitude']
            st.success("✅ 已取得定位！")

with col_show:
    st.write(f"目前設定座標：\n{st.session_state.lat:.4f}, {st.session_state.lon:.4f}")

st.divider()

# ====================== 4. 照片輸入區 ======================
col1, col2 = st.columns(2)
with col1:
    cam_in = st.camera_input("拍照辨識")
with col2:
    file_in = st.file_uploader("📁 上傳相片", type=["png", "jpg", "jpeg"])

img_file = cam_in if cam_in is not None else file_in

# ====================== 5. 主要邏輯 ======================
if img_file is not None:
    # AI 辨識部分 (維持你的 2.5 版本)
    if "ai_cache" not in st.session_state or st.session_state.get("last_img") != img_file.name:
        with st.spinner("🤖 AI 正在辨識中..."):
            try:
                model = genai.GenerativeModel('gemini-2.5-flash-lite')
                prompt = "請辨識照片中的植物。格式：中文名稱：xxx\n學名：xxx\n科別：xxx\n簡介：xxx（50字內）"
                response = model.generate_content([prompt, {"mime_type": img_file.type, "data": img_file.getvalue()}])
                st.session_state.ai_cache = response.text
                st.session_state.last_img = img_file.name
            except Exception as e:
                st.session_state.ai_cache = f"辨識失敗: {e}"

    ai_result = st.session_state.ai_cache
    st.info(ai_result)

    # 提取名稱
    default_name = ""
    if "中文名稱：" in ai_result:
        default_name = ai_result.split("中文名稱：")[1].split("\n")[0].strip()

    plant_name = st.text_input("確認植物名稱", value=default_name)

    # 上傳按鈕
    if st.button("🚀 確認並發布到地圖", type="primary"):
        try:
            with st.spinner("上傳中..."):
                ts = int(time.time())
                file_path = f"public/plant_{ts}.jpg"
                img_bytes = img_file.getvalue()
                supabase.storage.from_("plant-images").upload(path=file_path, file=img_bytes)
                img_url = supabase.storage.from_("plant-images").get_public_url(file_path)

                # 寫入資料庫 (使用剛剛取得的 GPS 座標)
                data = {
                    "name": plant_name,
                    "image_url": img_url,
                    "latitude": st.session_state.lat,
                    "longitude": st.session_state.lon,
                    "ai_result": ai_result
                }
                supabase.table("plants").insert(data).execute()
                st.balloons()
                st.success("🎉 上傳成功！")
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"錯誤：{e}")

# ====================== 6. 地圖展示 ======================
st.divider()
try:
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        st.map(df.rename(columns={"latitude": "lat", "longitude": "lon"}))
except:
    pass
