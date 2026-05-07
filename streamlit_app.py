import streamlit as st
import time

# --- 1. 照片輸入區 (兩種方式並存) ---
st.subheader("第一步：提供植物照片")

# 建立兩欄位，讓畫面好看一點
col1, col2 = st.columns(2)

with col1:
    cam_file = st.camera_input("直接拍照")

with col2:
    upload_file = st.file_uploader("選取檔案或手機拍照", type=["jpg", "png", "jpeg"])

# 判斷使用者是用哪種方式提供照片
img_file = cam_file if cam_file is not None else upload_file

# --- 2. 處理上傳邏輯 ---
if img_file is not None:
    st.image(img_file, caption="待上傳的照片", use_container_width=True)
    
    # 輸入植物名稱
    plant_name = st.text_input("這朵花/植物叫什麼名字？", placeholder="例如：百合花")
    
    if st.button("確認上傳成果"):
        if not plant_name:
            st.warning("請先輸入植物名稱喔！")
        else:
            with st.spinner("正在上傳至雲端..."):
                try:
                    # 產生唯一的檔名
                    file_name = f"{int(time.time())}_{img_file.name}"
                    file_path = f"public/{file_name}"
                    
                    # 讀取檔案內容
                    file_content = img_file.getvalue()
                    
                    # 1. 上傳到 Supabase Storage (儲存桶名稱請確認為 plant-images)
                    res = supabase.storage.from_("plant-images").upload(
                        path=file_path,
                        file=file_content,
                        file_options={"content-type": img_file.type}
                    )
                    
                    # 2. 取得公開網址
                    img_url = supabase.storage.from_("plant-images").get_public_url(file_path)
                    
                    # 3. 寫入資料庫 (假設你的 Table 叫 plants)
                    # 這裡建議加上經緯度(如有獲取)，否則先傳名稱與網址
                    data = {
                        "name": plant_name,
                        "image_url": img_url,
                        "created_at": "now()"
                    }
                    supabase.table("plants").insert(data).execute()
                    
                    st.success(f"🎉 成功！{plant_name} 已記錄在地圖上。")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"上傳失敗，錯誤訊息：{e}")
else:
    st.info("💡 提示：若無法開啟相機，請嘗試右側的「選取檔案」按鈕。")
