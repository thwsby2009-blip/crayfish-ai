import streamlit as st
from supabase import create_client, Client
import pandas as pd

# 1. 初始化 Supabase 連線
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
SUPABASE_KEY = "sb_publishable_2usRSc_p_POkI32j0RczJA_vz2smPM0"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("🌿 全民植物發現地圖")

# 1. 取得拍照檔案
img_file = st.camera_input("拍照或上傳植物發現成果")

# 2. 判斷是否有照片 (避免 NameError)
if img_file is not None:
    st.success("照片已讀取！")
    
    # 讓使用者輸入植物名稱
    plant_name = st.text_input("這朵植物叫什麼名字？", "未命名植物")
    
    if st.button("確認並上傳"):
        try:
            # 產生唯一檔名
            ts = int(time.time())
            file_name = f"{ts}_{img_file.name}"
            # 這裡就是你之前報錯的第 40 行，現在被包在 if 裡面了
            file_path = f"public/{file_name}"
            
            # 將圖片轉為 bytes
            img_bytes = img_file.getvalue()
            
            # --- A. 上傳到 Supabase Storage ---
            # 這裡請確保你的 bucket 名字叫做 'plant-images'
            storage_res = supabase.storage.from_("plant-images").upload(
                path=file_path,
                file=img_bytes,
                file_options={"content-type": img_file.type}
            )
            
            # 取得圖片公開網址
            img_url = supabase.storage.from_("plant-images").get_public_url(file_path)
            
            # --- B. 寫入資料庫 ---
            # 假設你已經用 get_geolocation 拿到了 loc (也可以先填預設值)
            new_data = {
                "name": plant_name,
                "image_url": img_url,
                "latitude": 25.0330,  # 測試用預設值，之後可接你的 GPS 變數
                "longitude": 121.5654
            }
            
            db_res = supabase.table("plants").insert(new_data).execute()
            
            st.balloons()
            st.success(f"🎉 上傳成功！你發現了 {plant_name}")
            
        except Exception as e:
            st.error(f"上傳過程發生錯誤: {e}")
else:
    st.info("💡 請點擊上方按鈕開啟相機拍照。")
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
