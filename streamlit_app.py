import streamlit as st
from supabase import create_client, Client
import time
import google.generativeai as genai
import pandas as pd
from streamlit_js_eval import get_geolocation
import uuid 
from PIL import Image
import io

# ====================== 0. 頁面基礎設定 (必須最先執行) ======================
st.set_page_config(page_title="植物發現地圖", layout="centered", page_icon="🌿")

# 錯誤捕捉機制：建立 session_state 用於儲存持久化錯誤，防止閃掉
if 'persistent_errors' not in st.session_state:
    st.session_state['persistent_errors'] = []

def log_error(msg):
    st.session_state['persistent_errors'].append(f"{time.strftime('%H:%M:%S')} - {msg}")
    st.error(msg)

# 在頁面最上方顯示所有捕捉到的錯誤
if st.session_state['persistent_errors']:
    with st.expander("⚠️ 系統錯誤日誌 (點擊展開)", expanded=True):
        for err in st.session_state['persistent_errors']:
            st.warning(err)
        if st.button("清除日誌"):
            st.session_state['persistent_errors'] = []
            st.rerun()

# ====================== 1. 核心設定與身分識別 ======================
SUPABASE_URL = "https://sxhhphxdkqxkjveqkwtc.supabase.co"
# 直接將 Key 寫入程式碼以確保連線正確，繞過 Secrets 設定問題
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN4aGhwaHhka3F4a2p2ZXFrd3RjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgwMjUxNTksImV4cCI6MjA5MzYwMTE1OX0.VgFCfb55KRv9RYdQE13GXjstue40mykP7I8kYiYfKtU"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase: Client = init_connection()
except Exception as e:
    log_error(f"Supabase 連接失敗: {e}")
    st.stop()

# ====================== 1-2. API Key 設定（表單式輸入）======================
st.markdown("---")
st.markdown("### 🔑 請輸入你的 API Key")

with st.form("api_key_form", clear_on_submit=False):
    st.markdown("**Gemini API Key**（免費申請：https://aistudio.google.com/apikey）")
    user_gemini_key = st.text_input(
        "GEMINI_API_KEY",
        type="password",
        placeholder="AIza...",
        label_visibility="collapsed"
    )
    st.markdown("*你的 API Key 不會被儲存，只用於本次操作*")
    submitted = st.form_submit_button("🚀 開始使用", use_container_width=True)

# 还没按按钮就停止
if not submitted:
    st.info("👆 填入 GEMINI API Key 後按「開始使用」")
    st.stop()

# 按了按鈕但沒填 key
if not user_gemini_key:
    log_error("❌ 請輸入 GEMINI API Key")
    st.stop()

# 設定 Gemini
try:
    genai.configure(api_key=user_gemini_key)
except Exception as e:
    log_error(f"Gemini 設定失敗: {e}")
    st.stop()

st.markdown("---")

# 🔒 產生或獲取當前使用者的唯一 ID
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = str(uuid.uuid4())

my_id = st.session_state['user_id']

# ====================== 新增：圖片壓縮工具函數 ======================
def compress_image(uploaded_file):
    """將圖片縮放並壓縮品質，解決手機照片過大的問題"""
    img = Image.open(uploaded_file)
    
    # 自動修正手機拍照的旋轉問題
    if hasattr(img, '_getexif') and img._getexif() is not None:
        from PIL import ExifTags
        exif = dict(img._getexif().items())
        orientation = next((k for k, v in ExifTags.TAGS.items() if v == 'Orientation'), None)
        if orientation in exif:
            if exif[orientation] == 3: img = img.rotate(180, expand=True)
            elif exif[orientation] == 6: img = img.rotate(270, expand=True)
            elif exif[orientation] == 8: img = img.rotate(90, expand=True)
            
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    img.thumbnail((1200, 1200)) # 限制最大寬度為 1200px
    
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=75) # 品質 75 是最佳平衡點
    return buffer.getvalue()

# ====================== 2. 介面樣式 (防止手機標題換行) ======================
st.markdown(
    """
    <style>
    h1 { font-size: 1.8rem !important; white-space: nowrap !important; }
    div[data-testid="stCameraInput"] button:first-child p { display: none !important; }
    div[data-testid="stCameraInput"] button:first-child::before {
        content: "📸 點擊拍照辨識" !important;
        visibility: visible !important;
        font-weight: bold !important;
        font-size: 1rem !important;
        color: inherit;
        display: block !important;
    }
    div[data-testid="stCameraInput"] button { min-height: 3rem !important; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🌿 全民植物發現地圖")

# ====================== 3. GPS 定位區 ======================
location = get_geolocation()
curr_lat, curr_lon = 25.0330, 121.5654 # 預設台北

if location:
    curr_lat = location['coords']['latitude']
    curr_lon = location['coords']['longitude']
    st.success(f"📍 定位成功：`{curr_lat:.4f}, {curr_lon:.4f}`")
else:
    st.warning("⚠️ 等待 GPS 定位中...（請確保已開啟瀏覽器定位權限）")

# ====================== 4. 照片輸入區 ======================
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

# ====================== 5. AI 辨識與上傳邏輯 ======================
if img_file is not None:
    st.image(img_file, width=350, caption="準備辨識的照片")
    
    img_id = f"{img_file.name}_{img_file.size}"
    
    if "ai_cache" not in st.session_state or st.session_state.get("last_img_id") != img_id:
        with st.spinner("🤖 Gemini 正在辨識植物..."):
            try:
                # 恢復為您指定的隱藏版模型 gemini-2.5-flash
                model = genai.GenerativeModel('gemini-2.5-flash') 
                prompt = "請詳細辨識此植物。格式：\\n中文名稱：xxx\\n學名：xxx\\n科別：xxx\\n簡介：xxx"
                
                response = model.generate_content([
                    prompt,
                    {"mime_type": "image/jpeg", "data": img_file.getvalue()}
                ])
                st.session_state.ai_cache = response.text
                st.session_state.last_img_id = img_id
                st.session_state.upload_done = False 
            except Exception as e:
                log_error(f"辨識出錯：{e}")
                st.session_state.ai_cache = "辨識失敗"

    ai_result = st.session_state.ai_cache
    st.info(f"💡 AI 辨識結果：\\n{ai_result}")

    parsed_name = ""
    if "中文名稱：" in ai_result:
        try:
            parsed_name = ai_result.split("中文名稱：")[1].split("\\n")[0].strip().replace("*", "")
        except:
            parsed_name = "未知植物"
    
    plant_name = st.text_input("確認植物名稱（AI 已自動填入，可修改）", value=parsed_name)

    if "upload_done" not in st.session_state:
        st.session_state.upload_done = False

    btn_label = "✅ 已成功上傳" if st.session_state.upload_done else "🚀 確認並上傳到地圖"
    
    if st.button(
        btn_label, 
        type="primary", 
        use_container_width=True, 
        disabled=st.session_state.upload_done
    ):
        if not plant_name.strip():
            st.warning("名稱不能為空！")
        else:
            try:
                with st.spinner("正在處理中..."):
                    final_img_data = compress_image(img_file)
                    
                    ts = int(time.time())
                    file_path = f"public/plant_{ts}.jpg"
                    
                    supabase.storage.from_("plant-images").upload(
                        path=file_path,
                        file=final_img_data,
                        file_options={"content-type": "image/jpeg"}
                    )
                    img_url = supabase.storage.from_("plant-images").get_public_url(file_path)

                    data = {
                        "name": plant_name.strip(),
                        "image_url": img_url,
                        "latitude": curr_lat,
                        "longitude": curr_lon,
                        "ai_result": ai_result,
                        "user_id": my_id
                    }
                    supabase.table("plants").insert(data).execute()

                    st.session_state.upload_done = True
                    st.balloons()
                    st.success("🎉 上傳成功！")
                    time.sleep(1.2)
                    st.rerun()
            except Exception as e:
                log_error(f"上傳失敗：{e}")

# ====================== 6. 地圖與歷史紀錄展示 (分月份管理) ======================
st.divider()

try:
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    all_plants = res.data

    if all_plants:
        df = pd.DataFrame(all_plants)
        df['created_at'] = pd.to_datetime(df['created_at'])
        
        st.subheader("📅 時光地圖：選擇觀測月份")
        df['month_year'] = df['created_at'].dt.strftime('%Y-%m')
        month_list = sorted(df['month_year'].unique().tolist(), reverse=True)
        month_list.insert(0, "全部紀錄")
        
        selected_month = st.selectbox("切換月份查看：", month_list)
        
        if selected_month != "全部紀錄":
            display_df = df[df['month_year'] == selected_month]
        else:
            display_df = df

        st.subheader(f"🌍 {selected_month} 植物分佈")
        map_data = display_df.rename(columns={"latitude": "lat", "longitude": "lon"})
        st.map(map_data)

        st.subheader(f"📍 {selected_month} 發現紀錄")
        filtered_plants = display_df.to_dict('records')

        for p in filtered_plants[:20]:
            with st.container():
                col_img, col_txt = st.columns([1, 2])
                with col_img:
                    st.image(p['image_url'], use_container_width=True)
                with col_txt:
                    is_mine = p.get('user_id') == my_id
                    col_header, col_del = st.columns([0.8, 0.2])
                    with col_header:
                        st.markdown(f"### {p['name']}")
                    
                    if is_mine:
                        with col_del:
                            if st.button("🗑️", key=f"del_{p['id']}"):
                                try:
                                    supabase.table("plants").delete().eq("id", p['id']).execute()
                                    st.success("已刪除")
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as e:
                                    log_error(f"刪除失敗: {e}")
                    else:
                        st.caption("🔒 唯讀模式")

                    st.caption(f"📅 {str(p['created_at'])[:16].replace('T', ' ')}")
                    g_url = f"https://www.google.com/maps/search/?api=1&query={p['latitude']},{p['longitude']}"
                    st.link_button("📍 在 Google 地圖查看位置", g_url, use_container_width=True)

                    with st.expander("查看辨識詳情"):
                        st.write(p.get('ai_result', '無詳細資料'))
                st.divider()
    else:
        st.info("目前尚無任何紀錄，快去拍第一張植物吧！")
except Exception as e:
    log_error(f"載入資料時發生錯誤：{e}")
