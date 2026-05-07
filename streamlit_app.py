import streamlit as st
from supabase import create_client, Client
import pandas as pd

# 1. 初始化 Supabase 連線
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
SUPABASE_KEY = "sb_publishable_2usRSc_p_POkI32j0RczJA_vz2smPM0"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("🌿 全民植物發現地圖")

# 2. 獲取手機 GPS 座標 (簡單版：讓使用者輸入，或使用進階套件)
# 註：為了手機操作方便，這裡先設計簡單的經緯度輸入欄位
st.subheader("1. 標記位置與拍照")
lat = st.number_input("緯度 (Latitude)", value=25.0330, format="%.6f")
lon = st.number_input("經度 (Longitude)", value=121.5654, format="%.6f")

# --- 拍照/選擇照片區塊 ---
picture = st.file_uploader("第一步：選取植物照片", type=["jpg", "png", "jpeg"])

# 只有當照片「已經選好」時，才會顯示後續的輸入框和按鈕
if picture is not None:
    # 1. 預覽照片
    st.image(picture, caption="待上傳的照片", use_container_width=True)
    
    # 2. 讓使用者輸入名字
    plant_name = st.text_input("第二步：這株植物叫什麼名字？", value="未知植物")
    
    # 3. 關鍵的上傳按鈕
    # 注意：這一行必須跟上面的 plant_name 對齊（有縮排）
    submit_button = st.button("第三步：點我上傳到地圖")
    
    if submit_button:
        st.info("正在連線資料庫並上傳圖片...")
        
        # 這裡是你原本寫的 Supabase 上傳邏輯（例如：supabase.storage.from...）
        # 請確保這裡的變數名稱也是用 picture
        # ... (你的上傳代碼)
        # A. 上傳圖片到 Supabase Storage
        file_path = f"public/{img_file.name}"
        response = supabase.storage.from_("plant-images").upload(file_path, img_file.getvalue())
        
        # B. 取得圖片公開網址
        img_url = supabase.storage.from_("plant-images").get_public_url(file_path)
        
        # C. 寫入資料庫
        data = {
            "name": plant_name,
            "latitude": lat,
            "longitude": lon,
            "image_url": img_url
        }
        supabase.table("plants").insert(data).execute()
        st.success(f"成功上傳：{plant_name}！")
        st.balloons()

# 4. 顯示地圖
st.subheader("2. 植物分佈地圖")
res = supabase.table("plants").select("name, latitude, longitude").execute()
if res.data:
    df = pd.DataFrame(res.data)
    st.map(df)
    st.write("目前的紀錄清單：", df)
