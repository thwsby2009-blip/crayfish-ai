import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import time
import pandas as pd
import uuid
# 這裡修正了：從套件中匯入函數
from streamlit_js_eval import streamlit_js_eval, get_geolocation

# 產生或獲取當前使用者的唯一 ID (存在瀏覽器中，重新整理不會消失，但關掉分頁可能會變)
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = str(uuid.uuid4())

my_id = st.session_state['user_id']

# ====================== 1. 核心設定 ======================
UPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
GEMINI_API_KEY = st.secrets.get("GEMINI_KEY")

if not GEMINI_API_KEY or not SUPABASE_KEY:
    st.error("❌ Secrets 金鑰缺失，請檢查設定。")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()
# ====================== 2. 介面中文化與樣式黑科技 ======================
st.set_page_config(page_title="植物發現地圖", layout="centered", page_icon="🌿")

st.markdown(
    """
    <style>
    /* 1. 隱藏相機按鈕原本的英文文字 */
    div[data-testid="stCameraInput"] button:first-child p {
        display: none !important;
    }

    /* 2. 在按鈕正中心注入中文 */
    div[data-testid="stCameraInput"] button:first-child::before {
        content: "📸 點擊拍照辨識" !important;
        visibility: visible !important;
        font-weight: bold !important;
        font-size: 1rem !important;
        color: inherit;
        display: block !important;
    }
    
    /* 3. 確保按鈕寬度自動適應 */
    div[data-testid="stCameraInput"] button {
        min-height: 3rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🌿 全民植物發現地圖")

# ====================== 恢復昨天的定位功能 ======================
st.subheader("📍 所在位置確認")

# 這裡呼叫昨天那個會動的工具
loc = get_geolocation()

if loc:
    curr_lat = loc['coords']['latitude']
    curr_lon = loc['coords']['longitude']
    st.success(f"✅ 定位成功：{curr_lat:.4f}, {curr_lon:.4f}")
else:
    curr_lat, curr_lon = 25.0330, 121.5654
    st.info("🛰️ 正在搜尋 GPS 訊號... (請確保手機已開啟定位並允許瀏覽器存取)")
    # 增加一個手動觸發按鈕，這是昨天維持穩定的關鍵
    if st.button("🔄 重新整理 GPS 座標"):
        st.rerun()

# 這裡可以加一個小地圖預覽目前位置，讓你確認它不是在 101
st.write(f"目前紀錄座標: {curr_lat}, {curr_lon}")
# ====================== 3. 照片輸入區 ======================
img_file = None
tab_cam, tab_file = st.tabs(["📸 啟動相機", "📁 從相簿上傳"])

with tab_cam:
    cam_in = st.camera_input("拍照後 AI 會自動辨識")
    if cam_in:
        img_file = cam_in

with tab_file:
    file_in = st.file_uploader("選擇植物照片", type=["jpg", "jpeg", "png"])
    if file_in and not img_file:
        img_file = file_in

# ====================== 4. AI 辨識與上傳邏輯 ======================
if img_file is not None:
    st.image(img_file, width=350, caption="準備辨識的照片")
    
    # 建立唯一 ID 防止重複觸發
    img_id = f"{img_file.name}_{img_file.size}"
    
    if "ai_cache" not in st.session_state or st.session_state.get("last_img_id") != img_id:
        with st.spinner("🤖 AI 正在努力辨識植物..."):
            try:
                model = genai.GenerativeModel('gemini-2.5-flash') 
                
                prompt = "請詳細辨識此植物。格式：\n中文名稱：xxx\n學名：xxx\n科別：xxx\n簡介：xxx（50字內）"
                
                response = model.generate_content([
                    prompt,
                    {"mime_type": "image/jpeg", "data": img_file.getvalue()}
                ])
                st.session_state.ai_cache = response.text
                st.session_state.last_img_id = img_id
            except Exception as e:
                st.error(f"辨識出錯：{e}")
                st.session_state.ai_cache = "辨識失敗"

    ai_result = st.session_state.ai_cache
    st.info(f"💡 AI 辨識建議：\n{ai_result}")

    # 解析中文名稱
    default_name = ""
    if "中文名稱：" in ai_result:
        try:
            default_name = ai_result.split("中文名稱：")[1].split("\n")[0].strip()
        except:
            default_name = ""

    plant_name = st.text_input("確認或修改名稱", value=default_name)

    if st.button("🚀 確認並上傳到地圖", type="primary", use_container_width=True):
        if not plant_name.strip():
            st.warning("請填寫植物名稱！")
        else:
            try:
                with st.spinner("正在上傳資料..."):
                    ts = int(time.time())
                    file_path = f"public/plant_{ts}.jpg"
                    
                    # 1. 上傳 Storage
                    supabase.storage.from_("plant-images").upload(
                        path=file_path,
                        file=img_file.getvalue(),
                        file_options={"content-type": "image/jpeg"}
                    )
                    img_url = supabase.storage.from_("plant-images").get_public_url(file_path)

                    # 2. 寫入資料庫 (已移除 ID 欄位)
                    data = {
                        "name": plant_name.strip(),
                        "image_url": img_url,
                        "latitude": curr_lat,
                        "longitude": curr_lon,
                        "ai_result": ai_result,
                        "user_id": my_id
                    }
                    supabase.table("plants").insert(data).execute()

                    st.balloons()
                    st.success(f"🎉 成功！「{plant_name}」已加入地圖。")
                    time.sleep(1.5)
                    st.rerun()
            except Exception as e:
                st.error(f"上傳失敗：{e}")

# ====================== 5. 地圖與歷史紀錄展示 ======================
st.divider()

try:
    # 讀取所有資料
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    all_plants = res.data

    if all_plants:
        st.subheader("🌍 植物分佈地圖")
        map_df = pd.DataFrame(all_plants)
        map_df = map_df.rename(columns={"latitude": "lat", "longitude": "lon"})
        st.map(map_df)

        st.subheader("📍 最近發現紀錄")
        for p in all_plants[:10]: # 顯示最近 10 筆
            with st.container():
                col_img, col_txt = st.columns([1, 2])
                with col_img:
                    st.image(p['image_url'], use_container_width=True)
                with col_txt:
                    st.markdown(f"### {p['name']}")
                    st.caption(f"📅 {p.get('created_at', '')[:16].replace('T', ' ')}")
                    
                    # 詳情與刪除按鈕
                    with st.expander("查看辨識詳情"):
                        st.write(p.get('ai_result', '無詳細資料'))
                    
                    # 刪除功能 (用唯一名稱當 key)
                    if st.button(f"🗑️ 刪除此紀錄", key=f"del_{p.get('id', p['created_at'])}"):
                        try:
                            # 1. 從資料庫刪除 (用 created_at 比對)
                            supabase.table("plants").delete().eq("created_at", p['created_at']).execute()
                            st.success("✅ 刪除成功！")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"刪除失敗：{e}")
                st.divider()
    else:
        st.info("地圖目前還沒有紀錄，快來當第一個貢獻者！")
except Exception as e:
    st.write("資料同步中...")
except Exception as e:
    st.write("資料同步中...")
