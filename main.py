import streamlit as st
from litellm import completion
import os

st.set_page_config(page_title="小龍蝦AI", layout="centered", page_icon="🦞")

# 初始化
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar
with st.sidebar:
    st.title("🦞 小龍蝦控制中心")

    user_key = st.text_input(
        "輸入 OpenRouter API Key",
        type="password"
    )

    model = st.selectbox(
        "選擇模型",
        [
            "openrouter/inclusionai/ling-2.6-1t:free",
            "openrouter/meta-llama/llama-3.1-8b-instruct:free",
            "openrouter/google/gemini-flash-1.5-exp:free",
        ]
    )

# 主畫面
st.title("💬 小龍蝦智能對話")

# 顯示對話
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 輸入
if prompt := st.chat_input("輸入訊息..."):

    if not user_key:
        st.error("請先輸入 API Key")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full = ""

            try:
                response = completion(
    model=model,
    messages=[
        {
            "role": "system",
            "content": "你是一位來自台灣的AI助手，請一律使用繁體中文回答，並使用台灣常用用語。"
        }
    ] + st.session_state.messages,
    api_key=user_key,
    stream=True
)

                for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        full += content
                        placeholder.markdown(full + "▌")

                placeholder.markdown(full)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full
                })

            except:
                st.error("AI 回應失敗")