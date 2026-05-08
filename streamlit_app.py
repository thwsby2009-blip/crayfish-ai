import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import time
import pandas as pd
import uuid
from streamlit_js_eval import streamlit_js_eval, get_geolocation
from PIL import Image
import io

# ====================== 1. 初始化與金鑰設定 (原版邏輯) ======================
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

if 'my_id' not in st.session_state:
    st.session_state.my_id = str(uuid.uuid4())
my_id = st.session_state.my_id

# ====================== 2. 標題與 GPS 座標 (顯示在標題下方) ======================
st.title("🌿 全台植物地圖 AI 辨識")

loc = get_geolocation()
if loc:
    curr_lat = loc['coords']['latitude']
    curr_lon = loc['coords']['longitude']
    st.markdown(f"📍 **當前座標**：`{curr_lat:.6f}, {curr_lon:.6f}`")
else:
    curr_lat, curr_lon = 25.0330, 121.5654
    st.caption("📍 正在獲取 GPS 座標中...")

# ====================== 3. 圖片輸入 (相機 + 手動上傳) ======================
st.divider()
source = st.radio("選擇來源：", ["相機拍照", "選取檔案"], horizontal=True)

if source == "相機拍照":
    uploaded_file = st.camera_input("拍照")
else:
    uploaded_file = st.file_uploader("選取圖片", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    with st.status("🚀 AI 辨識並上傳中...", expanded=True) as status:
        try:
            # --- A. 圖片壓縮 (避免太大導致上傳失敗) ---
            status.write("🖼️ 壓縮優化中...")
            img = Image.open(uploaded_file)
            img.thumbnail((1024, 1024), Image.LANCZOS)
            
            img_buffer = io.BytesIO()
            img.convert("RGB").save(img_buffer, format='JPEG', quality=75)
            compressed_bytes = img_buffer.getvalue()
            
            # --- B. 上傳到 Supabase Storage ---
            status.write("☁️ 儲存至 Supabase 雲端...")
            file_name = f"{int(time.time())}_{uuid.uuid4().hex[:4]}.jpg"
            
            # 確保你的 Supabase 有一個名為 "plant_images" 的 bucket
            supabase.storage.from_("plant_images").upload(
                file_name, compressed_bytes, {"content-type": "image/jpeg"}
            )
            img_url = supabase.storage.from_("plant_images").get_public_url(file_name)

            # --- C. AI 辨識 (指定使用 2.5-flash-lite) ---
            status.write("🧠 使用 gemini-2.5-flash-lite 分析...")
            model = genai.Generativeai.GenerativeModel('gemini-2.5-flash-lite')
            
            # 將圖片 bytes 轉回 PIL 給 AI 看
            ai_img = Image.open(io.BytesIO(compressed_bytes))
            response = model.generate_content([
                "你是一個植物學家。請辨識這張圖片中的植物名稱，並簡單說明其特徵與照顧方式。", 
                ai_img
            ])
            ai_result = response.text
            # 抓第一行作為名稱
            plant_name = ai_result.split('\n')[0].replace('#', '').strip()

            # --- D. 寫入資料庫 ---
            status.write("💾 寫入紀錄...")
            supabase.table("plants").insert({
                "name": plant_name,
                "image_url": img_url,
                "latitude": curr_lat,
                "longitude": curr_lon,
                "ai_result": ai_result,
                "user_id": my_id
            }).execute()
            
            status.update(label="✅ 辨識完成！", state="complete")
            st.success(f"辨識結果：{plant_name}")
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ 發生錯誤: {e}")

# ====================== 4. 地圖與紀錄管理 ======================
st.divider()
try:
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    if res.data:
        st.subheader("🌍 發現地圖")
        map_df = pd.DataFrame(res.data)
        st.map(map_df.rename(columns={"latitude": "lat", "longitude": "lon"}))

        st.subheader("📍 歷史紀錄")
        for p in res.data:
            with st.container():
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(p['image_url'], use_container_width=True)
                with c2:
                    st.markdown(f"### {p['name']}")
                    st.caption(f"📅 {p.get('created_at', '')[:10]}")
                    with st.expander("AI 辨識詳情"):
                        st.write(p['ai_result'])
                    
                    if str(p.get('user_id')) == str(my_id):
                        if st.button("🗑️ 刪除", key=f"del_{p.get('id')}"):
                            supabase.table("plants").delete().eq("id", p['id']).execute()
                            st.rerun()
                st.divider()
except Exception:
    st.info("地圖上目前沒有資料。")
