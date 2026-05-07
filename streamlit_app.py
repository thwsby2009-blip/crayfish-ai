import streamlit as st
from supabase import create_client, Client
import time
import google.generativeai as genai
import pandas as pd

# ====================== 1. 設定區 ======================
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
GEMINI_API_KEY = st.secrets.get("GEMINI_KEY")

if not GEMINI_API_KEY or not SUPABASE_KEY:
    st.error("❌ 金鑰讀取失敗")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# ====================== 2. 頁面佈局 ======================
st.set_page_config(page_title="植物地圖", layout="centered", page_icon="🌿")
st.title("🌿 全民植物發現地圖")

# ====================== 3. 拍照/上傳區 (修正重點) ======================
img_file = None

# 使用 Tabs 讓介面更乾淨，手機上按鈕會更明顯
tab1, tab2 = st.tabs(["📸 直接拍照", "📁 上傳照片"])

with tab1:
    # 這裡就是你說的按鍵名稱與標籤
    cam_in = st.camera_input("請將鏡頭對準植物")
    if cam_in:
        img_file = cam_in

with tab2:
    file_in = st.file_uploader("選擇手機相簿中的照片", type=["png", "jpg", "jpeg"])
    if file_in and not img_file:
        img_file = file_in

# ====================== 4. 主要邏輯 ======================
if img_file is not None:
    st.image(img_file, width=300)

    # 產生唯一的 Image ID (防止重複辨識)
    img_id = f"{img_file.name}_{img_file.size}"
    
    if "ai_cache" not in st.session_state or st.session_state.get("last_img_id") != img_id:
        with st.spinner("🤖 AI 正在辨識植物..."):
            try:
                # 使用你指定的 2.5 (或環境中唯一的可用模型)
                model = genai.GenerativeModel('gemini-2.0-flash-lite-preview-02-05') 
                
                prompt = "請辨識此植物。格式：\n中文名稱：xxx\n學名：xxx\n科別：xxx\n簡介：xxx（50字內）"

                response = model.generate_content([
                    prompt,
                    {"mime_type": "image/jpeg", "data": img_file.getvalue()}
                ])
                st.session_state.ai_cache = response.text
                st.session_state.last_img_id = img_id
            except Exception as e:
                st.error(f"辨識失敗：{e}")
                st.session_state.ai_cache = "辨識失敗"

    ai_result = st.session_state.ai_cache
    st.info(f"💡 辨識結果：\n{ai_result}")

    # 解析中文名稱
    default_name = ""
    if "中文名稱：" in ai_result:
        try:
            default_name = ai_result.split("中文名稱：")[1].split("\n")[0].strip()
        except:
            default_name = "未命名植物"

    # 使用者確認名稱
    plant_name = st.text_input("確認植物名稱", value=default_name)

    # 上傳按鈕
    if st.button("🚀 確認並發布到地圖", type="primary", use_container_width=True):
        if not plant_name.strip():
            st.warning("請輸入名稱！")
        else:
            try:
                with st.spinner("儲存中..."):
                    ts = int(time.time())
                    file_path = f"public/plant_{ts}.jpg"

                    # 上傳到 Storage
                    supabase.storage.from_("plant-images").upload(
                        path=file_path,
                        file=img_file.getvalue(),
                        file_options={"content-type": "image/jpeg"}
                    )
                    img_url = supabase.storage.from_("plant-images").get_public_url(file_path)

                    # 寫入資料庫
                    data = {
                        "name": plant_name.strip(),
                        "image_url": img_url,
                        "latitude": 25.0330,
                        "longitude": 121.5654,
                        "ai_result": ai_result
                    }
                    supabase.table("plants").insert(data).execute()

                    st.balloons()
                    st.success("🎉 已成功標記到地圖！")
                    time.sleep(1)
                    st.rerun() 
            except Exception as e:
                st.error(f"上傳出錯：{e}")

# ====================== 5. 地圖顯示 ======================
st.divider()
try:
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    if res.data:
        st.subheader("🌍 植物分佈地圖")
        df = pd.DataFrame(res.data)
        df_map = df.rename(columns={"latitude": "lat", "longitude": "lon"})
        st.map(df_map)
except:
    pass
