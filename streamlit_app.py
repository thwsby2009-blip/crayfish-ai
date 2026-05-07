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

# 3. 拍照功能
# 使用檔案上傳器，這在手機上相容性最好
picture = st.file_uploader("拍下照片或從相簿上傳", type=["jpg", "png", "jpeg"])

if picture:
    st.image(picture, caption="已選取的照片")

if img_file:
    plant_name = st.text_input("這株植物叫什麼名字？", "未知植物")
    
    if st.button("上傳發現紀錄"):
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
