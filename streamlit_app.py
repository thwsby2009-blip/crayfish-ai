import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import pandas as pd
import time
import uuid

# ====================== 1. 設定 ======================
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
GEMINI_KEY = st.secrets.get("GEMINI_KEY")

genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# ====================== 2. 頁面 ======================
st.set_page_config(page_title="植物發現地圖", layout="centered", page_icon="🌿")
st.title("🌿 全民植物發現地圖")

# ====================== 3. GPS（手機穩定版） ======================

st.subheader("📍 定位")

# 初始化預設（台北101）
if "lat" not in st.session_state:
    st.session_state.lat = 25.0330
    st.session_state.lon = 121.5654

# 👉 GPS Button（手機原生）
st.markdown("""
<button onclick="
navigator.geolocation.getCurrentPosition(
  function(pos){
    window.location.href = `?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`;
  },
  function(err){
    alert('GPS 失敗: ' + err.message);
  }
)
"
style="
padding:10px 20px;
font-size:16px;
background:#4CAF50;
color:white;
border:none;
border-radius:8px;
">
📍 取得目前位置
</button>
""", unsafe_allow_html=True)

# 讀 URL GPS
query = st.query_params

if "lat" in query and "lon" in query:
    try:
        st.session_state.lat = float(query["lat"])
        st.session_state.lon = float(query["lon"])
        st.success("✅ GPS 已更新")
    except:
        pass

st.write(f"目前座標：{st.session_state.lat:.5f}, {st.session_state.lon:.5f}")

st.divider()

# ====================== 4. 上傳區 ======================
col1, col2 = st.columns(2)

with col1:
    cam = st.camera_input("📸 拍照")

with col2:
    file = st.file_uploader("📁 上傳", type=["png", "jpg", "jpeg"])

img_file = cam if cam else file

# ====================== 5. AI 辨識 ======================
if img_file:

    st.image(img_file, width=300)

    # cache 避免重複跑 AI
    if "last_img" not in st.session_state or st.session_state.last_img != img_file.name:

        with st.spinner("🤖 AI 辨識中..."):
            model = genai.GenerativeModel("gemini-2.5-flash-lite")

            prompt = """
請辨識植物，請只輸出 JSON：

{
  "name_zh": "",
  "scientific_name": "",
  "family": "",
  "description": ""
}

規則：
- 不要解釋
- 不要多答案
- description 50字內
"""

            try:
                response = model.generate_content([
                    prompt,
                    {
                        "mime_type": img_file.type,
                        "data": img_file.getvalue()
                    }
                ])

                import json
                ai_data = json.loads(response.text)

            except:
                ai_data = {
                    "name_zh": "辨識失敗",
                    "scientific_name": "",
                    "family": "",
                    "description": response.text
                }

            st.session_state.ai_data = ai_data
            st.session_state.last_img = img_file.name

    ai_data = st.session_state.ai_data

    # 顯示
    st.markdown("### 🌱 辨識結果")
    st.write("中文名稱：", ai_data["name_zh"])
    st.write("學名：", ai_data["scientific_name"])
    st.write("科別：", ai_data["family"])
    st.write("簡介：", ai_data["description"])

    plant_name = st.text_input("確認名稱", value=ai_data["name_zh"])

    # ====================== 6. 上傳 ======================
    if st.button("🚀 上傳到地圖"):

        try:
            with st.spinner("上傳中..."):

                file_ext = "jpg"
                file_name = f"{uuid.uuid4().hex}.{file_ext}"

                img_bytes = img_file.getvalue()

                # upload image
                supabase.storage.from_("plant-images").upload(
                    file_name,
                    img_bytes,
                    {"content-type": img_file.type}
                )

                img_url = supabase.storage.from_("plant-images").get_public_url(file_name)

                # insert db
                data = {
                    "name": plant_name,
                    "image_url": img_url,
                    "latitude": st.session_state.lat,
                    "longitude": st.session_state.lon,
                    "ai_result": str(ai_data)
                }

                supabase.table("plants").insert(data).execute()

                st.success("🎉 上傳成功")
                st.balloons()

                st.rerun()

        except Exception as e:
            st.error(f"上傳失敗：{e}")

# ====================== 7. 最近紀錄 ======================
st.divider()
st.subheader("📍 最近發現")

try:
    res = supabase.table("plants").select("*").order("created_at", desc=True).limit(5).execute()

    for p in res.data:
        st.image(p["image_url"], width=200)
        st.write("🌱", p["name"])
        st.caption(p.get("created_at", "")[:16])
        st.divider()

except Exception as e:
    st.write("讀取失敗：", e)
