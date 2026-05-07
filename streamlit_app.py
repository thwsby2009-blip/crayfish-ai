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
st.write("拍照或上傳植物，AI 幫你辨識並標記在地圖上！")

# ====================== 3. 照片輸入區 ======================
col1, col2 = st.columns(2)
with col1:
    cam_in = st.camera_input("📸 拍照辨識")
with col2:
    file_in = st.file_uploader("📁 上傳相片", type=["png", "jpg", "jpeg"])

# 優先使用相機拍攝的照片，若無則使用上傳的照片
img_file = cam_in if cam_in is not None else file_in

# ====================== 4. 主要邏輯 ======================
if img_file is not None:
    st.image(img_file, width=300, caption="已讀取照片")

    # A. AI 辨識 (使用你指定的 2.5 版本模型)
    if "ai_cache" not in st.session_state or st.session_state.get("last_img") != img_file.name:
        with st.spinner("🤖 AI 正在辨識中..."):
            try:
                # 修正：強制指定為 2.5 版本
                model = genai.GenerativeModel('gemini-2.5-flash-lite')
                
                prompt = """請詳細辨識這張照片中的植物。回覆格式：
                中文名稱：xxx
                學名：xxx
                科別：xxx
                簡介：xxx（50字內）"""
                
                response = model.generate_content([
                    prompt,
                    {"mime_type": img_file.type, "data": img_file.getvalue()}
                ])
                st.session_state.ai_cache = response.text
                st.session_state.last_img = img_file.name
            except Exception as e:
                st.error(f"AI 辨識發生錯誤：{e}")
                st.session_state.ai_cache = "辨識失敗"

    ai_result = st.session_state.ai_cache
    st.info(f"💡 AI 辨識結果：\n{ai_result}")

    # B. 提取名稱
    default_name = ""
    if "中文名稱：" in ai_result:
        try:
            default_name = ai_result.split("中文名稱：")[1].split("\n")[0].strip()
        except:
            default_name = ""

    plant_name = st.text_input("確認或修改植物名稱", value=default_name)

    # C. 確認上傳按鈕 (縮排檢查)
    if st.button("🚀 確認並發布到地圖", type="primary"):
        if not plant_name:
            st.warning("請填寫植物名稱！")
        else:
            try:
                with st.spinner("正在上傳至雲端儲存空間..."):
                    ts = int(time.time())
                    file_path = f"public/plant_{ts}.jpg"

                    # 上傳照片
                    img_bytes = img_file.getvalue()
                    supabase.storage.from_("plant-images").upload(
                        path=file_path,
                        file=img_bytes,
                        file_options={"content-type": "image/jpeg"}
                    )
                    img_url = supabase.storage.from_("plant-images").get_public_url(file_path)

                    # 寫入資料庫 (移除手動 ID，交給資料庫自動生成)
                    data = {
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
                st.error(f"上傳失敗原因：{e}")

# ====================== 5. 地圖與紀錄展示 ======================
st.divider()

try:
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    records = res.data

    if records:
        st.subheader("🌍 植物分佈地圖")
        df = pd.DataFrame(records)
        df_map = df.rename(columns={"latitude": "lat", "longitude": "lon"})
        st.map(df_map)

        st.subheader("📍 最近發現紀錄")
        for p in records[:10]:
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
        st.info("目前地圖上還沒有資料。")
except Exception as e:
    st.write("資料同步中...")
