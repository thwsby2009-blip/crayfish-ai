import streamlit as st
from supabase import create_client, Client
import time

# 1. 初始化 Supabase 連線
# 請確保這兩個值是你從 Supabase 後台複製過來的真實內容
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
SUPABASE_KEY = "sb_publishable_2usRSc_p_POkI32j0RczJA_vz2smPM0"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# --- 網頁介面開始 ---
st.set_page_config(page_title="植物發現地圖", layout="centered")
st.title("🌿 全民植物發現地圖")
st.write("拍下你身邊的植物，分享給全世界！")

# 2. 拍照/上傳組件
img_file = st.camera_input("第一步：請拍下植物的照片")

# 3. 核心邏輯：判斷是否有照片
if img_file is not None:
    st.success("✅ 照片已成功讀取")
    
    # 讓使用者輸入資訊
    plant_name = st.text_input("第二步：這朵植物叫什麼名字？", placeholder="例如：百合花")
    
    # 建立上傳按鈕
    if st.button("第三步：確認並上傳成果"):
        try:
            with st.spinner("正在上傳中，請稍候..."):
                # A. 處理檔名
                ts = int(time.time())
                # 確保檔名沒有特殊字元，使用時間戳記最安全
                file_ext = img_file.name.split(".")[-1]
                file_name = f"plant_{ts}.{file_ext}"
                file_path = f"public/{file_name}"
                
                # B. 上傳圖片到 Storage
                img_bytes = img_file.getvalue()
                supabase.storage.from_("plant-images").upload(
                    path=file_path,
                    file=img_bytes,
                    file_options={"content-type": img_file.type}
                )
                
                # C. 取得圖片的公開網址
                img_url = supabase.storage.from_("plant-images").get_public_url(file_path)
                
                # D. 將資料寫入資料庫 Table
                # 提示：這裡暫時用固定經緯度，之後可以再加入 GPS 功能
                data = {
                    "name": plant_name,
                    "image_url": img_url,
                    "latitude": 25.0330,
                    "longitude": 121.5654
                }
                
                supabase.table("plants").insert(data).execute()
                
                st.balloons()
                st.success(f"🎉 太棒了！'{plant_name}' 已成功標記在地圖上！")
                
        except Exception as e:
            st.error(f"❌ 上傳失敗，原因：{e}")
            st.info("請檢查 Supabase 的 Storage 是否已建立 'plant-images' 儲存桶，並設為 Public。")

else:
    st.info("💡 提示：請點擊上方的按鈕開啟相機拍照，拍照後才會出現填寫名稱的欄位。")

# --- 下方可以放地圖顯示 (選配) ---
st.divider()
st.subheader("📍 最近的發現")
# 這裡簡單列出資料庫內容
try:
    response = supabase.table("plants").select("*").order("created_at", desc=True).limit(5).execute()
    for plant in response.data:
        st.write(f"🌱 {plant['name']} (上傳時間: {plant.get('created_at', '未知')})")
except:
    st.write("暫時還沒有發現紀錄。")
