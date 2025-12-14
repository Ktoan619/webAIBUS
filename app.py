import streamlit as st
import google.generativeai as genai
import streamlit.components.v1 as components
import re
from gtts import gTTS
import io

# Import dữ liệu từ file data (đảm bảo file data_and_prompts.py nằm cùng thư mục)
from data_and_prompts import BUS_DATA, get_full_system_instruction

# --- 1. CẤU HÌNH TRANG & CSS (MÀU XANH LÁ + CHỮ ĐEN) ---
st.set_page_config(
    page_title="VnBus Green AI",
    page_icon="🍃",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS tùy chỉnh giao diện: Xanh lá chủ đạo, Chữ đen tương phản cao
st.markdown("""
<style>
    /* Nền trang xanh nhạt */
    .stApp {
        background-color: #ecfdf5; /* Emerald-50 */
    }
    
    /* Chỉnh màu chữ đen toàn bộ */
    h1, h2, h3, h4, h5, h6, p, div, span, label {
        color: #000000 !important;
    }
    
    /* Input field */
    .stTextInput > div > div > input {
        background-color: #ffffff;
        color: #000000;
        border: 2px solid #10b981; /* Emerald-500 */
        border-radius: 10px;
    }
    
    /* Chat message box */
    .stChatMessage {
        background-color: #ffffff;
        border-radius: 15px;
        border: 1px solid #d1fae5;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        color: #000000;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #10b981 !important; /* Emerald-500 */
        color: white !important;
        font-weight: bold;
        border-radius: 10px;
        border: none;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        background-color: #059669 !important; /* Emerald-600 */
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #10b981;
    }
    
    /* Audio player */
    audio {
        width: 100%;
        height: 30px;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. HÀM HỖ TRỢ (TTS & AUDIO) ---
def text_to_speech_stream(text):
    """Chuyển văn bản thành giọng nói Google (Tiếng Việt)"""
    try:
        # Xử lý text để đọc tự nhiên hơn (bỏ ký tự lạ)
        clean_text = re.sub(r'[*_#]', '', text)
        tts = gTTS(text=clean_text, lang='vi')
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        return audio_fp
    except Exception as e:
        return None

# --- 3. STATE MANAGEMENT ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Xin chào! Mình là Trợ lý Giao thông Xanh 🍃. Bạn muốn đi đâu hôm nay?"}
    ]
if "selected_route" not in st.session_state:
    st.session_state.selected_route = None
if "custom_route" not in st.session_state:
    st.session_state.custom_route = None

# --- 4. HÀM XỬ LÝ HTML MAP ---
def render_map_html(route_data, api_key=None, is_custom=False):
    # CASE A: CÓ API KEY
    if api_key:
        src = ""
        if is_custom:
            origin = route_data['origin']
            dest = route_data['destination']
            src = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={origin}&destination={dest}&mode=transit"
        else:
            origin = route_data['stops'][0]
            dest = route_data['stops'][-1]
            waypoints = "|".join(route_data['stops'][1:-1])
            src = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={origin},Vietnam&destination={dest},Vietnam&waypoints={waypoints}&mode=transit"
            
        return f"""<div style="width:100%; height:500px; border-radius:15px; overflow:hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border: 2px solid #10b981;"><iframe width="100%" height="100%" frameborder="0" style="border:0" src="{src}" allowfullscreen></iframe></div>"""

    # CASE B: KHÔNG CÓ KEY (MÔ PHỎNG)
    stops = route_data['stops'] if not is_custom else [route_data['origin'], "Trạm trung chuyển", "Trạm kết nối", route_data['destination']]
    color = route_data.get('color', '#8b5cf6') if not is_custom else '#8b5cf6'
    
    timeline_html = ""
    for idx, stop in enumerate(stops):
        bg_color = color if idx == 0 else (color if idx == len(stops)-1 else '#d1fae5')
        text_color = "white" if idx == 0 or idx == len(stops)-1 else "#065f46"
        timeline_html += f"""
        <div style="display:flex; align-items:start; margin-bottom: 20px; position:relative;">
            <div style="width:30px; height:30px; background-color:{bg_color}; border-radius:50%; border:3px solid #ffffff; box-shadow:0 2px 4px rgba(0,0,0,0.2); z-index:10; display:flex; align-items:center; justify-content:center; color:{text_color}; font-weight:bold; font-size:12px;">{idx+1}</div>
            <div style="margin-left:15px; background:white; padding:10px 15px; border-radius:10px; border:1px solid #10b981; width:100%; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-weight:bold; color:#000000;">{stop}</div>
            </div>
            {'<div style="position:absolute; left:14px; top:30px; bottom:-25px; width:4px; background-color:#d1fae5; z-index:0;"></div>' if idx != len(stops)-1 else ''}
        </div>"""

    return f"""
        <div style="background-color:#ffffff; padding:20px; border-radius:15px; height:500px; overflow-y:auto; border:2px solid #10b981;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; padding-bottom:10px; border-bottom:1px solid #ecfdf5;">
                <span style="font-weight:bold; color:#064e3b; font-size: 1.1em;">🗺️ Lộ trình mô phỏng</span>
                <span style="font-size:10px; background:#dcfce7; color:#065f46; padding:4px 10px; border-radius:20px; border:1px solid #10b981; font-weight:bold;">Simulation Mode</span>
            </div>
            {timeline_html}
            <div style="text-align:center; margin-top:20px; font-size:12px; color:#ef4444; font-weight:bold;">⚠️ Nhập API Key để xem bản đồ thực tế.</div>
        </div>"""

# --- 5. GIAO DIỆN SIDEBAR ---
with st.sidebar:
    st.title("🌿 VnBus AI")
    st.markdown("---")
    
    # Logic đọc key
    maps_key = st.secrets.get("GOOGLE_MAPS_KEY", "")
    if not maps_key:
        maps_key = st.text_input("🔑 Google Maps Key", type="password", placeholder="AIzaSy...")
    else:
        st.success("✅ Đã nạp Maps Key")

    gemini_key = st.secrets.get("GEMINI_KEY", "")
    if not gemini_key:
        gemini_key = st.text_input("✨ Gemini API Key", type="password", placeholder="AI Key...")
    else:
        st.success("✅ Đã nạp Gemini Key")
    
    st.markdown("---")
    
    # Cài đặt giọng nói
    st.subheader("🔊 Cài đặt giọng nói")
    enable_tts = st.checkbox("Bot tự động đọc (Google Voice)", value=True)
    
    mode = st.radio("Chế độ:", ["Trợ lý Chat 🤖", "Tìm đường 📍"])

# --- 6. LOGIC CHÍNH ---
col1, col2 = st.columns([1, 1.3])

with col1:
    if mode == "Trợ lý Chat 🤖":
        st.subheader("💬 Trợ lý VnBus")
        chat_container = st.container(height=450)
        
        # Hiển thị lịch sử chat
        with chat_container:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    # Nếu là tin nhắn của bot và có audio, hiển thị audio player
                    if msg["role"] == "assistant" and "audio" in msg:
                        st.audio(msg["audio"], format="audio/mp3")

        # Input Chat
        prompt = st.chat_input("Nhập tin nhắn...")
        
        # Audio Input (Nếu có) - Streamlit mới hỗ trợ st.audio_input
        # audio_val = st.audio_input("Hoặc nói để hỏi...") # Uncomment nếu dùng Streamlit bản mới nhất
        
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"):
                    st.write(prompt)

            response_text = ""
            bot_audio = None
            
            # Logic tìm kiếm nội bộ
            found_bus = next((b for b in BUS_DATA if b['id'] == prompt or b['id'] == prompt.upper()), None)
            
            if found_bus:
                st.session_state.selected_route = found_bus
                st.session_state.custom_route = None
                response_text = f"🚌 **Đã tìm thấy Tuyến {found_bus['name']}**\n\n💰 Giá: `{found_bus['price']}`\n⏰ Giờ: `{found_bus['time']}`\n📍 Lộ trình: {', '.join(found_bus['stops'])}"
                
            elif gemini_key:
                try:
                    genai.configure(api_key=gemini_key)
                    full_instruction = get_full_system_instruction()
                    model = genai.GenerativeModel('gemini-2.0-flash-exp', system_instruction=full_instruction)
                    
                    gemini_history = []
                    for msg in st.session_state.messages[:-1]:
                        role = "user" if msg["role"] == "user" else "model"
                        gemini_history.append({"role": role, "parts": [str(msg["content"])]})
                    
                    chat = model.start_chat(history=gemini_history)
                    response = chat.send_message(prompt)
                    raw_text = response.text
                    
                    # Xử lý lệnh vẽ map
                    map_cmd_match = re.search(r"MAP_CMD:\s*(.*?)\s*\|\s*(.*)", raw_text)
                    if map_cmd_match:
                        origin_point = map_cmd_match.group(1).strip()
                        dest_point = map_cmd_match.group(2).strip()
                        st.session_state.custom_route = {
                            "origin": origin_point, "destination": dest_point,
                            "stops": [], "duration": "Đang tính...", "distance": "..."
                        }
                        st.session_state.selected_route = None
                        response_text = raw_text.replace(map_cmd_match.group(0), "").strip()
                        if not response_text: response_text = f"Đang tìm đường từ {origin_point} đến {dest_point}..."
                    else:
                        response_text = raw_text
                except Exception as e:
                    response_text = f"⚠️ Lỗi kết nối AI: {e}"
            else:
                response_text = "⚠️ Tôi không tìm thấy tuyến này. Hãy nhập đúng Mã số xe (VD: 152) hoặc nhập Gemini Key để hỏi thông minh hơn."

            # Tạo giọng đọc (TTS)
            msg_data = {"role": "assistant", "content": response_text}
            if enable_tts and response_text:
                audio_bytes = text_to_speech_stream(response_text[:500]) # Đọc 500 ký tự đầu để nhanh
                if audio_bytes:
                    msg_data["audio"] = audio_bytes

            st.session_state.messages.append(msg_data)
            st.rerun()

    else: # Chế độ Tìm đường
        st.subheader("📍 Tìm lộ trình")
        with st.form("route_form"):
            origin = st.text_input("Điểm đi", placeholder="VD: Chợ Bến Thành")
            destination = st.text_input("Điểm đến", placeholder="VD: Landmark 81")
            submitted = st.form_submit_button("Tìm đường ngay 🚀")
            
            if submitted and origin and destination:
                st.session_state.selected_route = None
                st.session_state.custom_route = {
                    "origin": origin, "destination": destination,
                    "stops": [], "duration": "Calculating...", "distance": "..."
                }
                st.success(f"Đã tìm thấy lộ trình từ {origin} đến {destination}")
                st.rerun()

# Cột Phải: Map
with col2:
    st.subheader("🗺️ Bản đồ trực quan")
    target_data = st.session_state.custom_route or st.session_state.selected_route
    is_custom = True if st.session_state.custom_route else False
        
    if target_data:
        map_html = render_map_html(target_data, api_key=maps_key, is_custom=is_custom)
        components.html(map_html, height=520, scrolling=False)
        
        if not is_custom:
            c1, c2 = st.columns(2)
            c1.info(f"💰 Giá vé: {target_data['price']}")
            c2.warning(f"⏰ Thời gian: {target_data['time']}")
            if gemini_key and st.button("✨ Gợi ý điểm vui chơi trên tuyến này"):
                with st.spinner("AI đang phân tích..."):
                    try:
                        genai.configure(api_key=gemini_key)
                        model = genai.GenerativeModel('gemini-2.0-flash-exp')
                        res = model.generate_content(f"Tuyến xe buýt: {target_data['name']} đi qua {', '.join(target_data['stops'])}. Gợi ý 3 địa điểm ăn chơi gần đó. Dùng emoji.")
                        st.success(res.text)
                        
                        # Đọc kết quả gợi ý
                        if enable_tts:
                            audio = text_to_speech_stream(res.text)
                            if audio: st.audio(audio)
                    except: st.error("Lỗi kết nối AI.")
    else:
        st.markdown("""<div style="background:#ffffff; height:500px; border-radius:15px; display:flex; align-items:center; justify-content:center; flex-direction:column; color:#000000; border: 2px dashed #10b981;"><div style="font-size:50px;">🍃</div><h3>Chưa có lộ trình</h3><p style="color:#000000;">Hãy hỏi bot hoặc nhập điểm đi/đến</p></div>""", unsafe_allow_html=True)
