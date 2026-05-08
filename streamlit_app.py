import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import time
import pandas as pd
import uuid
from streamlit_js_eval import streamlit_js_eval, get_geolocation
from PIL import Image
import io

# ====================== 1. 初始化與金鑰設定 (保持你的原樣) ======================
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

# ====================== 2. 獲取地理位置 (GPS 核心) ======================
loc = get_geolocation()
if loc:
    curr_lat = loc['coords']['latitude']
    curr_lon = loc['coords']['longitude']
    st.success(f"📍 GPS 定位成功: {curr_lat:.4f}, {curr_lon:.4f}")
else:
    curr_lat, curr_lon = 25.0330, 121.5654
    st.warning("⚠️ 無法取得精確位置，將使用預設座標")

# ====================== 3. 圖片輸入 (相機 + 手動上傳) ======================
st.title("🌿 全台植物地圖 AI 辨識")

# 提供兩種方式：相機拍照 或 檔案上傳
source = st.radio("選擇圖片來源：", ["使用相機", "上傳圖片檔案"])
if source == "使用相機":
    uploaded_file = st.camera_input("拍照辨識植物")
else:
    uploaded_file = st.file_uploader("請選擇圖片檔案", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    with st.status("🚀 辨識處理中...", expanded=True):
        # --- A. 壓縮圖片 ---
        img = Image.open(uploaded_file)
        img.thumbnail((1024, 1024), Image.LANCZOS)
        img_buffer = io.BytesIO()
        img.convert("RGB").save(img_buffer, format='JPEG', quality=70)
        compressed_bytes = img_buffer.getvalue()
        
        # --- B. 上傳至 Storage ---
        file_name = f"{int(time.time())}.jpg"
        supabase.storage.from_("plant_images").upload(file_name, compressed_bytes, {"content-type": "image/jpeg"})
        img_url = supabase.storage.from_("plant_images").get_public_url(file_name)

        # --- C. 辨識 (絕對使用 gemini-2.5-flash-lite) ---
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        # 給 AI 辨識也用壓縮後的圖，速度最快
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
        
        st.success("✅ 辨識完成並已儲存！")
        time.sleep(1)
        st.rerun()

# ====================== 4. 地圖與紀錄管理 (含刪除) ======================
st.divider()
try:
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    if res.data:
        st.subheader("🌍 植物分佈地圖")
        map_df = pd.DataFrame(res.data)
        st.map(map_df.rename(columns={"latitude": "lat", "longitude": "lon"}))

        st.subheader("📍 歷史紀錄")
        for p in res.data:
            with st.container():
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.image(p['image_url'], use_container_width=True)
                with col2:
                    st.markdown(f"### {p['name']}")
                    st.caption(f"📅 {p.get('created_at', '')[:10]}")
                    with st.expander("查看 AI 詳細報告"):
                        st.write(p['ai_result'])
                    
                    # 本人刪除按鈕
                    if str(p.get('user_id')) == str(my_id):
                        if st.button("🗑️ 刪除", key=f"del_{p.get('id')}"):
                            supabase.table("plants").delete().eq("id", p['id']).execute()
                            st.rerun()
                st.divider()
except Exception as e:
    st.info("目前地圖尚無資料")
