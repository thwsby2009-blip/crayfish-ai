import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import time
import pandas as pd
import uuid
from streamlit_js_eval import streamlit_js_eval, get_geolocation
from PIL import Image
import io

# ====================== 1. 初始化與金鑰設定 ======================
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

# ====================== 2. 標題與 GPS 座標顯示 ======================
st.title("🌿 全台植物地圖 AI 辨識")

# 獲取地理位置
loc = get_geolocation()
if loc:
    curr_lat = loc['coords']['latitude']
    curr_lon = loc['coords']['longitude']
    # 放在標題下方的座標顯示
    st.markdown(f"📍 **當前座標**：`{curr_lat:.6f}, {curr_lon:.6f}`")
else:
    curr_lat, curr_lon = 25.0330, 121.5654
    st.caption("📍 正在獲取 GPS 座標中... (或請開啟定位權限)")

st.caption(f"設備 ID: {my_id[:8]}")

# ====================== 3. 圖片輸入 (相機 + 手動上傳) ======================
st.divider()
source = st.radio("選擇圖片來源：", ["使用相機拍照", "從相簿選取檔案"], horizontal=True)

if source == "使用相機拍照":
    uploaded_file = st.camera_input("拍照辨識植物")
else:
    uploaded_file = st.file_uploader("請選擇圖片檔案", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    with st.status("🚀 AI 辨識中...", expanded=True) as status:
        try:
            # --- A. 圖片壓縮 (節省 Storage 空間) ---
            status.write("🖼️ 優化圖片檔案大小...")
            img = Image.open(uploaded_file)
            img.thumbnail((1024, 1024), Image.LANCZOS)
            
            img_buffer = io.BytesIO()
            img.convert("RGB").save(img_buffer, format='JPEG', quality=70)
            compressed_bytes = img_buffer.getvalue()
            
            # --- B. 上傳至 Supabase Storage ---
            status.write("☁️ 儲存圖片至雲端...")
            file_name = f"{int(time.time())}_{uuid.uuid4().hex[:4]}.jpg"
            supabase.storage.from_("plant_images").upload(
                file_name, compressed_bytes, {"content-type": "image/jpeg"}
            )
            img_url = supabase.storage.from_("plant_images").get_public_url(file_name)

            # --- C. AI 辨識 (使用 2.5-flash-lite) ---
            status.write("🧠 使用 Gemini 2.5-flash-lite 分析...")
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            
            response = model.generate_content([
                "你是一個植物學家。請辨識這張圖片中的植物名稱，並簡單說明其特徵與照顧方式。", 
                Image.open(io.BytesIO(compressed_bytes))
            ])
            ai_result = response.text
            plant_name = ai_result.split('\n')[0].replace('#', '').strip()

            # --- D. 寫入 Database ---
            status.write("💾 記錄地理位置與辨識結果...")
            supabase.table("plants").insert({
                "name": plant_name,
                "image_url": img_url,
                "latitude": curr_lat,
                "longitude": curr_lon,
                "ai_result": ai_result,
                "user_id": my_id
            }).execute()
            
            status.update(label="✅ 紀錄成功！", state="complete")
            st.success(f"發現植物：{plant_name}")
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ 處理失敗: {e}")

# ====================== 4. 地圖與歷史紀錄展示 ======================
st.divider()
try:
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    if res.data:
        st.subheader("🌍 全台發現地圖")
        map_df = pd.DataFrame(res.data)
        st.map(map_df.rename(columns={"latitude": "lat", "longitude": "lon"}))

        st.subheader("📍 最近辨識紀錄")
        for p in res.data:
            with st.container():
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.image(p['image_url'], use_container_width=True)
                with col2:
                    st.markdown(f"### {p['name']}")
                    st.caption(f"📅 {p.get('created_at', '')[:10]} | 📍 {p.get('latitude', 0):.4f}, {p.get('longitude', 0):.4f}")
                    with st.expander("查看 AI 辨識詳細內容"):
                        st.write(p['ai_result'])
                    
                    # 只有本人可以刪除
                    if str(p.get('user_id')) == str(my_id):
                        if st.button("🗑️ 刪除", key=f"del_{p.get('id')}"):
                            supabase.table("plants").delete().eq("id", p['id']).execute()
                            st.rerun()
                st.divider()
except Exception:
    st.info("地圖目前尚無植物紀錄")
