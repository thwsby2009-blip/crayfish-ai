import streamlit as st
from supabase import create_client, Client
import time
import google.generativeai as genai

# ====================== 設定區 ======================
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
SUPABASE_KEY = "sb_publishable_2usRSc_p_POkI32j0RczJA_vz2smPM0"

# 把你的 Gemini API Key 放在這裡（推薦使用 st.secrets）
GEMINI_API_KEY = st.secrets.get("GEMINI_KEY", None)   # 建議這樣寫

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    st.error("❌ 未設定 GEMINI_KEY，請在 Streamlit Cloud 的 Secrets 中設定")

# 初始化 Supabase
@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# ====================== 頁面設定 ======================
st.set_page_config(page_title="植物發現地圖", layout="centered", page_icon="🌿")
st.title("🌿 全民植物發現地圖")
st.write("拍下植物，AI 幫你辨識！")

# ====================== 拍照 / 上傳 ======================
col1, col2 = st.columns(2)

with col1:
    img_file = st.camera_input("📸 拍攝植物照片")

with col2:
    if img_file is None:
        img_file = st.file_uploader("📁 或從相簿選擇照片", 
                                   type=["png", "jpg", "jpeg", "heic"])

# ====================== 主要邏輯 ======================
if img_file is not None:
    st.success("✅ 照片已成功讀取")
    st.image(img_file, width=300)

    # 呼叫 Gemini 辨識
    with st.spinner("🤖 AI 正在辨識植物..."):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')  # 可改成 gemini-1.5-pro 如果需要更高準確度
            
            prompt = """請詳細辨識這張照片中的植物。
            請用以下格式回覆：
            中文名稱：xxx
            學名：xxx
            科別：xxx
            簡介：xxx（50字以內）"""

            response = model.generate_content([
                prompt,
                {
                    "mime_type": img_file.type,
                    "data": img_file.getvalue()
                }
            ])
            
            ai_result = response.text
            st.info(f"🌱 AI 辨識結果：\n{ai_result}")
            
        except Exception as e:
            st.error(f"AI 辨識失敗：{e}")
            ai_result = "AI 辨識失敗"

    # 使用者確認名稱
    plant_name = st.text_input(
        "植物名稱（可修改）", 
        value=ai_result.split("中文名稱：")[1].split("\n")[0] if "中文名稱：" in ai_result else "",
        placeholder="請輸入或修改植物名稱"
    )

    # 上傳按鈕
    if st.button("✅ 確認並上傳到地圖", type="primary"):
        if not plant_name.strip():
            st.error("請輸入植物名稱")
        else:
            try:
                with st.spinner("正在上傳..."):
                    ts = int(time.time())
                    file_ext = img_file.type.split("/")[-1] if "/" in img_file.type else "jpg"
                    file_name = f"plant_{ts}.{file_ext}"
                    file_path = f"public/{file_name}"

                    # 上傳到 Supabase Storage
                    img_bytes = img_file.getvalue()
                    supabase.storage.from_("plant-images").upload(
                        path=file_path,
                        file=img_bytes,
                        file_options={"content-type": img_file.type}
                    )

                    img_url = supabase.storage.from_("plant-images").get_public_url(file_path)

                    # 寫入資料庫
                    data = {
                        "name": plant_name.strip(),
                        "image_url": img_url,
                        "latitude": 25.0330,   # 之後可改成真實 GPS
                        "longitude": 121.5654,
                        "ai_result": ai_result
                    }

                    supabase.table("plants").insert(data).execute()

                    st.balloons()
                    st.success(f"🎉 上傳成功！「{plant_name}」已標記在地圖上！")

            except Exception as e:
                st.error(f"上傳失敗：{e}")

else:
    st.info("💡 請使用上方按鈕拍照或從相簿選取照片")

# ====================== 最近發現 ======================
st.divider()
st.subheader("📍 最近的植物發現")
try:
    response = supabase.table("plants").select("*").order("created_at", desc=True).limit(5).execute()
    for plant in response.data:
        st.image(plant['image_url'], width=200)
        st.write(f"🌱 **{plant['name']}**")
        st.caption(f"上傳時間：{plant.get('created_at', '未知')[:16]}")
        st.divider()
except:
    st.write("目前還沒有發現紀錄。")
