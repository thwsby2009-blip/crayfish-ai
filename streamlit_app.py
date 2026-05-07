import streamlit as st
from supabase import create_client, Client
import time
import google.generativeai as genai
import pandas as pd

# ====================== 1. 設定區 ======================
# 從 Secrets 讀取金鑰，這樣最安全
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
GEMINI_API_KEY = st.secrets.get("GEMINI_KEY")

if not GEMINI_API_KEY or not SUPABASE_KEY:
    st.error("❌ 金鑰讀取失敗，請檢查 Streamlit Cloud 的 Secrets 設定。")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

# 初始化 Supabase 連線
@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# ====================== 2. 頁面佈局 ======================
st.set_page_config(page_title="植物發現地圖", layout="centered", page_icon="🌿")
st.title("🌿 全民植物發現地圖")
st.write("拍下植物，AI 幫你辨識並在地圖上留下紀錄！")

# ====================== 3. 照片輸入 ======================
col1, col2 = st.columns(2)
with col1:
    cam_in = st.camera_input("📸 拍攝植物")
with col2:
    file_in = st.file_uploader("📁 選取相片", type=["png", "jpg", "jpeg"])

img_file = cam_in if cam_in is not None else file_in

# ====================== 4. AI 辨識邏輯 ======================
if img_file is not None:
    st.image(img_file, width=300, caption="已選取照片")

   # 使用 Session State 確保改名字時不會重新跑 AI 辨識
    if "ai_cache" not in st.session_state or st.session_state.get("last_img") != img_file.name:
        with st.spinner("🤖 AI 正在辨識中..."):
            try:
                # 這裡改用最通用的模型名稱，並加上報錯捕捉
                model = genai.GenerativeModel('gemini-1.5-flash-latest') 
                
                prompt = """請辨識照片中的植物。回覆格式：
                中文名稱：xxx
                學名：xxx
                科別：xxx
                簡介：xxx（50字內）"""
                
                # 取得照片內容
                img_data = img_file.getvalue()
                
                response = model.generate_content([
                    prompt,
                    {"mime_type": "image/jpeg", "data": img_data}
                ])
                
                if response.text:
                    st.session_state.ai_cache = response.text
                    st.session_state.last_img = img_file.name
                else:
                    st.session_state.ai_cache = "AI 回傳內容為空"
                    
            except Exception as e:
                # 這裡會印出真正的錯誤原因，請跟我說這行顯示什麼
                st.error(f"❌ 辨識出錯原因：{str(e)}") 
                st.session_state.ai_cache = "辨識失敗"

    ai_result = st.session_state.ai_cache
    st.info(f"💡 AI 辨識結果：\n{ai_result}")

    # 自動提取中文名稱
    default_name = ""
    if "中文名稱：" in ai_result:
        default_name = ai_result.split("中文名稱：")[1].split("\n")[0].strip()

    plant_name = st.text_input("確認或修改植物名稱", value=default_name)

    # ====================== 5. 上傳與寫入 ======================
    if st.button("🚀 確認並上傳到地圖", type="primary"):
        if not plant_name:
            st.warning("請填寫植物名稱！")
        else:
            try:
                with st.spinner("正在上傳至雲端..."):
                    # A. 檔名處理
                    ts = int(time.time())
                    file_path = f"public/plant_{ts}.jpg"

                    # B. 上傳照片到 Storage
                    img_bytes = img_file.getvalue()
                    supabase.storage.from_("plant-images").upload(
                        path=file_path,
                        file=img_bytes,
                        file_options={"content-type": "image/jpeg"}
                    )
                    img_url = supabase.storage.from_("plant-images").get_public_url(file_path)

                    # C. 寫入資料庫 (手動給 id)
                    data = {
                        "id": str(ts),
                        "name": plant_name,
                        "image_url": img_url,
                        "latitude": 25.0330,
                        "longitude": 121.5654,
                        "ai_result": ai_result
                    }
                    supabase.table("plants").insert(data).execute()

                    st.balloons()
                    st.success("🎉 上傳成功！")
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"上傳失敗：{e}")

# ====================== 6. 地圖與紀錄展示 ======================
st.divider()

try:
    # 抓取資料庫所有紀錄
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    records = res.data

    if records:
        st.subheader("🌍 植物分佈地圖")
        df = pd.DataFrame(records)
        # Streamlit 地圖需要 lat, lon 欄位名稱
        df_map = df.rename(columns={"latitude": "lat", "longitude": "lon"})
        st.map(df_map)

        st.subheader("📍 最近發現")
        for p in records[:5]:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.image(p['image_url'], use_container_width=True)
            with c2:
                st.write(f"### {p['name']}")
                st.caption(f"📅 {p.get('created_at', '')[:16].replace('T', ' ')}")
                with st.expander("查看 AI 詳細分析"):
                    st.write(p.get('ai_result', ''))
            st.divider()
    else:
        st.info("目前還沒有資料點，快去拍第一張吧！")
except Exception as e:
    st.write("載入地圖中...")
