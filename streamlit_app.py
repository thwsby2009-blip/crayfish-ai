import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import time
import pandas as pd
import uuid
from streamlit_js_eval import streamlit_js_eval, get_geolocation
from PIL import Image
import io

# ====================== 1. 初始化與金鑰設定 (保持原樣) ======================
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co" 
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") 
GEMINI_API_KEY = st.secrets.get("GEMINI_KEY") 

if not GEMINI_API_KEY or not SUPABASE_KEY: 
    st.error("❌ Secrets 金鑰缺失，請檢查設定。") 
    st.stop() 

genai.configure(api_key=GEMINI_API_KEY) 

@st.cache_resource 
def init_connection(): 
    return create_client(SUPABASE_URL, SUPABASE_KEY) 

supabase: Client = init_connection()

# 設備身分識別
if 'my_id' not in st.session_state:
    st.session_state.my_id = str(uuid.uuid4())
my_id = st.session_state.my_id

# ====================== 2. 獲取地理位置 ======================
loc = get_geolocation()
curr_lat = loc['coords']['latitude'] if loc else 25.0330
curr_lon = loc['coords']['longitude'] if loc else 121.5654

# ====================== 3. 圖片處理與辨識 (精簡整合版) ======================
st.title("🌿 全台植物地圖 AI 辨識")

uploaded_file = st.camera_input("拍照辨識植物")

if uploaded_file is not None:
    with st.status("🚀 辨識中...", expanded=True):
        # --- A. 壓縮圖片 (新增的部分) ---
        img = Image.open(uploaded_file)
        img.thumbnail((1024, 1024), Image.LANCZOS)
        img_buffer = io.BytesIO()
        img.convert("RGB").save(img_buffer, format='JPEG', quality=70)
        compressed_bytes = img_buffer.getvalue()
        
        # --- B. 上傳 (使用壓縮後的檔案) ---
        file_name = f"{int(time.time())}.jpg"
        supabase.storage.from_("plant_images").upload(file_name, compressed_bytes, {"content-type": "image/jpeg"})
        img_url = supabase.storage.from_("plant_images").get_public_url(file_name)

        # --- C. 辨識 (使用你指定的 2.5-lite) ---
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        response = model.generate_content([
            "你是一個植物學家。請辨識這張圖片中的植物名稱，並簡單說明其特徵與照顧方式。", 
            Image.open(io.BytesIO(compressed_bytes))
        ])
        ai_result = response.text
        plant_name = ai_result.split('\n')[0].replace('#', '').strip()

        # --- D. 存入資料庫 ---
        supabase.table("plants").insert({
            "name": plant_name, "image_url": img_url,
            "latitude": curr_lat, "longitude": curr_lon,
            "ai_result": ai_result, "user_id": my_id
        }).execute()
        
        st.rerun()

# ====================== 4. 地圖與歷史紀錄 (保持原樣) ======================
st.divider()
res = supabase.table("plants").select("*").order("created_at", desc=True).execute()

if res.data:
    st.subheader("🌍 植物分佈地圖")
    st.map(pd.DataFrame(res.data).rename(columns={"latitude": "lat", "longitude": "lon"}))

    for p in res.data:
        with st.container():
            col1, col2 = st.columns([1, 2])
            with col1: st.image(p['image_url'])
            with col2:
                st.markdown(f"### {p['name']}")
                with st.expander("辨識詳情"): st.write(p['ai_result'])
                
                # 本人刪除按鈕
                if str(p.get('user_id')) == str(my_id):
                    if st.button("🗑️ 刪除", key=f"del_{p.get('id')}"):
                        supabase.table("plants").delete().eq("id", p['id']).execute()
                        st.rerun()
            st.divider()
