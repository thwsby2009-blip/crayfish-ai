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
    st.stop() genai.configure(api_key=GEMINI_API_KEY) 
    @st.cache_resource 
    def init_connection(): 
        return create_client(SUPABASE_URL, SUPABASE_KEY) 
        supabase: Client = init_connection()

# 設備身分識別 (User ID) - 確保每台手機有獨立 ID
if 'my_id' not in st.session_state:
    st.session_state.my_id = str(uuid.uuid4())
my_id = st.session_state.my_id

# ====================== 2. 獲取地理位置 ======================
loc = get_geolocation()
if loc:
    curr_lat = loc['coords']['latitude']
    curr_lon = loc['coords']['longitude']
else:
    # 預設位置 (台北)
    curr_lat = 25.0330
    curr_lon = 121.5654

# ====================== 3. 圖片處理、壓縮與辨識 ======================
st.title("🌿 全台植物地圖 AI 辨識")
st.caption(f"你的設備 ID: {my_id[:8]}...")

uploaded_file = st.camera_input("拍照辨識植物")

if uploaded_file is not None:
    with st.status("🚀 正在處理圖片並辨識...", expanded=True) as status:
        try:
            # --- A. 圖片壓縮 ---
            status.write("🖼️ 正在優化圖片大小 (壓縮中)...")
            original_img = Image.open(uploaded_file)
            
            # 縮放：保持比例，長邊最大 1024 像素
            max_size = 1024
            original_img.thumbnail((max_size, max_size), Image.LANCZOS)
            
            # 轉成 RGB 並以 JPEG 70% 品質壓縮
            img_byte_arr = io.BytesIO()
            original_img.convert("RGB").save(img_byte_arr, format='JPEG', quality=70)
            compressed_bytes = img_byte_arr.getvalue()
            
            # --- B. 上傳至 Supabase Storage ---
            status.write("☁️ 正在上傳至雲端...")
            file_name = f"{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
            
            # 使用壓縮後的 bytes 上傳
            supabase.storage.from_("plant_images").upload(
                file_name, 
                compressed_bytes, 
                {"content-type": "image/jpeg"}
            )
            
            # 獲取公開網址
            img_url = supabase.storage.from_("plant_images").get_public_url(file_name)

            # --- C. 使用 Gemini AI 辨識 ---
            status.write("🧠 AI 正在分析植物特徵...")
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            # 使用壓縮後的圖片進行辨識
            img_for_ai = Image.open(io.BytesIO(compressed_bytes))
            
            response = model.generate_content([
                "你是一個植物學家。請辨識這張圖片中的植物名稱，並簡單說明其特徵與照顧方式。", 
                img_for_ai
            ])
            ai_result = response.text
            plant_name = ai_result.split('\n')[0].replace('#', '').strip()

            # --- D. 寫入資料庫 ---
            status.write("💾 儲存紀錄至地圖...")
            data = {
                "name": plant_name,
                "image_url": img_url,
                "latitude": curr_lat,
                "longitude": curr_lon,
                "ai_result": ai_result,
                "user_id": my_id
            }
            supabase.table("plants").insert(data).execute()
            
            status.update(label="✅ 辨識完成！", state="complete", expanded=False)
            st.success(f"辨識成功：{plant_name}")
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"發生錯誤：{e}")
            status.update(label="❌ 處理失敗", state="error")

# ====================== 4. 地圖與歷史紀錄展示 ======================
st.divider()

try:
    # 抓取所有紀錄
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    all_plants = res.data

    if all_plants:
        st.subheader("🌍 植物分佈地圖")
        map_df = pd.DataFrame(all_plants)
        if not map_df.empty:
            map_df = map_df.rename(columns={"latitude": "lat", "longitude": "lon"})
            st.map(map_df)

        st.subheader("📍 最近發現紀錄")
        
        for p in all_plants:
            with st.container():
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.image(p['image_url'], use_container_width=True)
                with col2:
                    st.markdown(f"### {p['name']}")
                    st.caption(f"📅 {p.get('created_at', '')[:16].replace('T', ' ')}")
                    
                    with st.expander("查看 AI 辨識報告"):
                        st.write(p.get('ai_result', '無詳細資料'))
                    
                    # 刪除功能 (僅限本人)
                    if str(p.get('user_id')) == str(my_id):
                        # 萬用 ID 抓取
                        row_id = p.get('id') or p.get('ID') or p.get('created_at')
                        if st.button(f"🗑️ 刪除紀錄", key=f"del_{row_id}"):
                            # 執行刪除
                            if p.get('id'):
                                supabase.table("plants").delete().eq("id", p['id']).execute()
                            else:
                                supabase.table("plants").delete().eq("created_at", p['created_at']).execute()
                            st.success("已刪除！")
                            time.sleep(0.5)
                            st.rerun()
                st.divider()
    else:
        st.info("地圖上還沒有資料，快來拍一張吧！")

except Exception as e:
    st.write("目前尚無資料或連線異常")
