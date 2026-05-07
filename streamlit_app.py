import streamlit as st
from supabase import create_client, Client
import time
import google.generativeai as genai
import pandas as pd

# ====================== 1. 設定區 ======================
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
# 從 Secrets 讀取金鑰
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
st.write("拍下植物，AI 幫你辨識並標記在地圖上！")

# ====================== 3. 照片輸入 ======================
col1, col2 = st.columns(2)
with col1:
    cam_in = st.camera_input("📸 拍攝植物照片")
with col2:
    file_in = st.file_uploader("📁 或從相簿選擇照片", type=["png", "jpg", "jpeg"])

# 決定使用哪張照片
img_file = cam_in if cam_in is not None else file_in

# ====================== 4. 主要邏輯 ======================
if img_file is not None:
    st.success("✅ 照片已成功讀取")
    st.image(img_file, width=300)

    # A. 呼叫 Gemini 辨識 (使用 Session State 防止重複執行)
    if "ai_cache" not in st.session_state or st.session_state.get("last_img") != img_file.name:
        with st.spinner("🤖 AI 正在辨識植物..."):
            try:
                # 這裡使用你確認可以運行的模型名稱
                model = genai.GenerativeModel('gemini-2.0-flash-lite-preview-02-05') 
                
                prompt = """請詳細辨識這張照片中的植物。
                請用以下格式回覆：
                中文名稱：xxx
                學名：xxx
                科別：xxx
                簡介：xxx（50字以內）"""

                response = model.generate_content([
                    prompt,
                    {"mime_type": img_file.type, "data": img_file.getvalue()}
                ])
                st.session_state.ai_cache = response.text
                st.session_state.last_img = img_file.name
            except Exception as e:
                st.error(f"AI 辨識失敗：{e}")
                st.session_state.ai_cache = "辨識失敗"

    ai_result = st.session_state.ai_cache
    st.info(f"🌱 AI 辨識建議：\n{ai_result}")

    # B. 解析中文名稱作為預設值
    default_name = ""
    if "中文名稱：" in ai_result:
        try:
            default_name = ai_result.split("中文名稱：")[1].split("\n")[0].strip()
        except:
            default_name = ""

    # 使用者確認或修改名稱
    plant_name = st.text_input("確認植物名稱", value=default_name)

    # C. 上傳與寫入邏輯
    if st.button("🚀 確認並發布到地圖", type="primary"):
        if not plant_name.strip():
            st.warning("請先輸入植物名稱喔！")
        else:
            try:
                with st.spinner("正在儲存資料..."):
                    # 1. 處理檔名
                    ts = int(time.time())
                    file_ext = img_file.type.split("/")[-1] if "/" in img_file.type else "jpg"
                    file_path = f"public/plant_{ts}.{file_ext}"

                    # 2. 上傳照片到 Storage
                    img_bytes = img_file.getvalue()
                    supabase.storage.from_("plant-images").upload(
                        path=file_path,
                        file=img_bytes,
                        file_options={"content-type": img_file.type}
                    )
                    img_url = supabase.storage.from_("plant-images").get_public_url(file_path)

                    # 3. 寫入資料庫 (移除 id，由資料庫自動產生)
                    data = {
                        "name": plant_name.strip(),
                        "image_url": img_url,
                        "latitude": 25.0330,  # 目前暫時寫死
                        "longitude": 121.5654,
                        "ai_result": ai_result
                    }

                    supabase.table("plants").insert(data).execute()

                    st.balloons()
                    st.success(f"🎉 成功！「{plant_name}」已加入地圖。")
                    time.sleep(1)
                    st.rerun() 

            except Exception as e:
                st.error(f"上傳過程中發生錯誤：{e}")

# ====================== 5. 地圖與紀錄展示 ======================
st.divider()

try:
    # 讀取資料庫現有資料
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    all_plants = res.data

    if all_plants:
        # A. 展示地圖
        st.subheader("🌍 植物分佈地圖")
        map_df = pd.DataFrame(all_plants)
        map_df = map_df.rename(columns={"latitude": "lat", "longitude": "lon"})
        st.map(map_df)

        # B. 展示最近紀錄
        st.subheader("📍 最近發現紀錄")
        for p in all_plants[:10]: # 顯示最近 10 筆
            with st.container():
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(p['image_url'], use_container_width=True)
                with c2:
                    st.write(f"### {p['name']}")
                    st.caption(f"📅 {p.get('created_at', '未知')[:16].replace('T', ' ')}")
                    with st.expander("查看辨識詳情"):
                        st.write(p.get('ai_result', '無資料'))
                st.divider()
    else:
        st.info("地圖上目前還沒有紀錄，快來當第一個貢獻者吧！")

except Exception as e:
    st.write("資料載入中...")
