import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import time
import pandas as pd
import uuid
# 這裡修正了：從套件中匯入函數
from streamlit_js_eval import streamlit_js_eval, get_geolocation
from PIL import Image 
import io

# 產生或獲取當前使用者的唯一 ID (存在瀏覽器中，重新整理不會消失，但關掉分頁可能會變)
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = str(uuid.uuid4())

my_id = st.session_state['user_id']

import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import time
import pandas as pd
import uuid
from streamlit_js_eval import streamlit_js_eval, get_geolocation
from PIL import Image
import io

# ====================== 1. 初始化與金鑰設定 ======================
# 請確保你的 secrets 裡面有這些資訊
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# 設備身分識別 (User ID)
if 'my_id' not in st.session_state:
    # 這裡可以根據需要調整 UUID 的持久性邏輯
    st.session_state.my_id = str(uuid.uuid4())
my_id = st.session_state.my_id

# ====================== 2. 獲取地理位置 ======================
loc = get_geolocation()
curr_lat = loc['coords']['latitude'] if loc else 25.0330
curr_lon = loc['coords']['longitude'] if loc else 121.5654

# ====================== 3. 圖片處理與辨識 ======================
st.title("🌿 全台植物地圖 AI 辨識")
uploaded_file = st.camera_input("拍照辨識植物")

if uploaded_file is not None:
    with st.status("🚀 處理中，請稍候...", expanded=True) as status:
        # --- A. 圖片壓縮手術 ---
        status.write("🖼️ 正在優化圖片大小...")
        original_img = Image.open(uploaded_file)
        
        # 縮放：保持比例，長邊最大 1024 像素
        max_size = 1024
        original_img.thumbnail((max_size, max_size), Image.LANCZOS)
        
        # 轉成 RGB (確保 JPEG 格式相容) 並壓縮
        img_byte_arr = io.BytesIO()
        # quality=70 是平衡畫質與檔案大小的最佳點
        original_img.convert("RGB").save(img_byte_arr, format='JPEG', quality=70)
        compressed_bytes = img_byte_arr.getvalue()
        
        # --- B. 上傳至 Supabase Storage ---
        status.write("☁️ 正在上傳至雲端...")
        file_name = f"{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
        
        # 注意：這裡傳入的是壓縮後的 compressed_bytes
        supabase.storage.from_("plant_images").upload(
            file_name, 
            compressed_bytes, 
            {"content-type": "image/jpeg"}
        )
        
        # 獲取公開網址
        img_url = supabase.storage.from_("plant_images").get_public_url(file_name)

        # --- C. 使用 Gemini AI 辨識 ---
        status.write("🧠 AI 正在辨識植物...")
        model = genai.GenerativeModel('gemini-1.5-flash')
        # 直接使用壓縮後的圖片給 AI 辨識 (速度更快)
        img_for_ai = Image.open(io.BytesIO(compressed_bytes))
        
        response = model.generate_content([
            "你是一個植物學家。請辨識這張圖片中的植物名稱，並簡單說明其特徵與照顧方式。", 
            img_for_ai
        ])
        ai_result = response.text
        plant_name = ai_result.split('\n')[0].replace('#', '').strip()

        # --- D. 寫入資料庫 ---
        status.write("💾 儲存紀錄中...")
        data = {
            "name": plant_name,
            "image_url": img_url,
            "latitude": curr_lat,
            "longitude": curr_lon,
            "ai_result": ai_result,
            "user_id": my_id
        }
        supabase.table("plants").insert(data).execute()
        
        status.update(label="✅ 辨識完成！", state="complete", expanded=False)
        st.success(f"辨識成功：{plant_name}")
        st.rerun()

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
    # 從資料庫抓取最新資料
    res = supabase.table("plants").select("*").order("created_at", desc=True).execute()
    all_plants = res.data

    if all_plants:
        st.subheader("🌍 植物分佈地圖")
        # 準備地圖資料
        map_df = pd.DataFrame(all_plants)
        if not map_df.empty:
            # 確保經緯度欄位名稱符合 st.map 要求
            map_df = map_df.rename(columns={"latitude": "lat", "longitude": "lon"})
            st.map(map_df)

        st.subheader("📍 最近發現紀錄")
        
        # 顯示最近的 10 筆紀錄
        for p in all_plants[:10]:
            with st.container():
                col_img, col_txt = st.columns([1, 2])
                
                with col_img:
                    st.image(p['image_url'], use_container_width=True)
                
                with col_txt:
                    st.markdown(f"### {p['name']}")
                    st.caption(f"📅 {p.get('created_at', '')[:16].replace('T', ' ')}")
                    
                    # 詳情摺疊區
                    with st.expander("查看辨識詳情"):
                        st.write(p.get('ai_result', '無詳細資料'))
                    
                    # --- 刪除權限檢查區 ---
                    # 檢查這張圖的 user_id 是否等於現在這台設備的 my_id
                    if str(p.get('user_id')) == str(my_id):
                        # 找到可用的唯一識別碼 (id 或 ID 或 created_at)
                        row_id = p.get('id') or p.get('ID') or p.get('created_at')
                        
                        if st.button(f"🗑️ 刪除我的紀錄", key=f"del_{row_id}"):
                            try:
                                # 自動偵測欄位名稱並執行刪除
                                if p.get('id'):
                                    delete_res = supabase.table("plants").delete().eq("id", p['id']).execute()
                                elif p.get('ID'):
                                    delete_res = supabase.table("plants").delete().eq("ID", p['ID']).execute()
                                else:
                                    delete_res = supabase.table("plants").delete().eq("created_at", p['created_at']).execute()
                                
                                # 檢查是否真的刪除成功
                                if delete_res.data and len(delete_res.data) > 0:
                                    st.success("✅ 紀錄已成功刪除！")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ 刪除失敗：請檢查 Supabase 是否開啟了 RLS 保護 (需改為 Disable)")
                            except Exception as e:
                                st.error(f"⚠️ 刪除時發生錯誤：{e}")
                    else:
                        st.caption("🔒 唯讀紀錄 (非本人上傳)")
                
                st.divider()
    else:
        st.info("地圖上還沒有植物紀錄，快去拍第一張吧！")

except Exception as e:
    st.error(f"讀取紀錄時發生錯誤：{e}")
