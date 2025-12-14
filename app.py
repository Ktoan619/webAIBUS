import streamlit as st
import google.generativeai as genai
import streamlit.components.v1 as components
import re
from gtts import gTTS
import io
import requests
import time
from streamlit_js_eval import get_geolocation

# Import dữ liệu từ file data
from data_and_prompts import BUS_DATA, get_full_system_instruction

# --- 1. CẤU HÌNH TRANG & CSS (MÀU XANH LÁ + CHỮ ĐEN) ---
st.set_page_config(
    page_title="VnBus Green AI Pro",
    page_icon="🍃",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #ecfdf5; }
    h1, h2, h3, h4, h5, h6, p, div, span, label, li { color: #000000 !important; }
    .stTextInput > div > div > input {
        background-color: #ffffff; color: #000000; border: 2px solid #10b981; border-radius: 10px;
    }
    .stChatMessage {
        background-color: #ffffff; border-radius: 15px; border: 1px solid #d1fae5;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); color: #000000;
    }
    .stButton > button {
        background-color: #10b981 !important; color: white !important; font-weight: bold;
        border-radius: 10px; border: none; transition: all 0.3s;
    }
    .stButton > button:hover {
        background-color: #059669 !important; transform: translateY(-2px);
    }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #10b981; }
    audio { width: 100%; height: 30px; margin-top: 5px; }
    
    /* Highlight box cho chỉ dẫn đường */
    .direction-box {
        background-color: #d1fae5; border-left: 5px solid #059669;
        padding: 15px; border-radius: 5px; margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CÁC HÀM XỬ LÝ API & LOGIC ---

def text_to_speech_stream(text):
    """Chuyển văn bản thành giọng nói (Memory Stream)"""
    try:
        clean_text = re.sub(r'[*_#<>]', '', text) # Làm sạch markdown & html
        tts = gTTS(text=clean_text, lang='vi')
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        return audio_fp
    except: return None

def get_google_directions_text(origin, destination, api_key):
    """Gọi Google API lấy chỉ dẫn chi tiết dạng văn bản (Backend)"""
    if not api_key: return None, None
    try:
        # 1. Tìm đường đi bộ/xe buýt
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": origin,
            "destination": destination,
            "mode": "transit",
            "transit_mode": "bus",
            "language": "vi",
            "key": api_key
        }
        resp = requests.get(url, params=params).json()
        
        if resp["status"] != "OK": return None, f"Lỗi Google Maps: {resp['status']}"
        
        # 2. Phân tích steps để lấy hướng dẫn
        leg = resp["routes"][0]["legs"][0]
        duration = leg["duration"]["text"]
        distance = leg["distance"]["text"]
        
        steps_info = []
        summary = f"🚌 Lộ trình: {distance} ({duration}).\n"
        
        for step in leg["steps"]:
            instruction = re.sub('<[^<]+?>', '', step["html_instructions"]) # Bỏ HTML tag
            if step["travel_mode"] == "TRANSIT":
                bus_line = step["transit_details"]["line"]["short_name"]
                headsign = step["transit_details"]["headsign"]
                steps_info.append(f"🚍 Bắt xe {bus_line} (hướng {headsign}): {instruction}")
            elif step["travel_mode"] == "WALKING":
                steps_info.append(f"🚶 {instruction}")
        
        full_text = summary + "\n".join(steps_info)
        return full_text, None
    except Exception as e:
        return None, str(e)

# --- 3. QUẢN LÝ TRẠNG THÁI (STATE) ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Xin chào! Bạn muốn đi đâu? (Có thể nói 'Từ vị trí của tôi' để dùng GPS)"}]
if "selected_route" not in st.session_state: st.session_state.selected_route = None
if "custom_route" not in st.session_state: st.session_state.custom_route = None
if "user_location" not in st.session_state: st.session_state.user_location = None

# --- 4. GIAO DIỆN SIDEBAR ---
with st.sidebar:
    st.title("🌿 VnBus Pro")
    st.markdown("---")
    
    # API Keys
    maps_key = st.secrets.get("GOOGLE_MAPS_KEY", "") or st.text_input("🔑 Google Maps Key", type="password")
    gemini_key = st.secrets.get("GEMINI_KEY", "") or st.text_input("✨ Gemini API Key", type="password")
    
    st.markdown("---")
    st.subheader("📡 Định vị GPS")
    
    # Nút lấy vị trí (Sử dụng streamlit_js_eval)
    if st.checkbox("Sử dụng Vị trí hiện tại"):
        loc = get_geolocation()
        if loc:
            lat = loc['coords']['latitude']
            lng = loc['coords']['longitude']
            st.session_state.user_location = f"{lat},{lng}"
            st.success(f"📍 Đã định vị: {lat:.4f}, {lng:.4f}")
        else:
            st.warning("Đang chờ tín hiệu GPS...")

    st.markdown("---")
    enable_tts = st.checkbox("🔊 Đọc to câu trả lời", value=True)
    mode = st.radio("Chế độ:", ["Chat & Chỉ đường 🤖", "Tra cứu Tuyến 🚌"])

# --- 5. HÀM RENDER MAP (IFRAME) ---
def render_map_html(origin, destination, api_key):
    if api_key:
        src = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={origin}&destination={destination}&mode=transit"
        return f"""<div style="width:100%; height:400px; border-radius:15px; overflow:hidden; border: 2px solid #10b981;"><iframe width="100%" height="100%" frameborder="0" style="border:0" src="{src}" allowfullscreen></iframe></div>"""
    return """<div style="padding:20px; text-align:center; border:2px dashed #ccc;">⚠️ Cần API Key để hiện bản đồ</div>"""

# --- 6. LOGIC CHÍNH ---
col1, col2 = st.columns([1, 1.2])

with col1:
    if mode == "Chat & Chỉ đường 🤖":
        st.subheader("💬 Trợ lý Thông minh")
        chat_container = st.container(height=450)
        
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"], unsafe_allow_html=True)
                if msg.get("audio"): st.audio(msg["audio"], format="audio/mp3")

        prompt = st.chat_input("Nhập nơi muốn đến (VD: Đi đến Chợ Bến Thành)...")
        
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"): st.write(prompt)

            response_text = ""
            origin_coords = None
            dest_point = None
            
            # Logic AI phân tích
            if gemini_key:
                try:
                    genai.configure(api_key=gemini_key)
                    # Prompt nâng cấp: Nhận diện "Vị trí của tôi"
                    sys_prompt = get_full_system_instruction() + "\n\nQUAN TRỌNG: Nếu người dùng nói 'từ đây', 'vị trí của tôi', hãy trả về MAP_CMD với điểm đi là 'CURRENT_LOC'."
                    
                    model = genai.GenerativeModel('gemini-2.0-flash-exp', system_instruction=sys_prompt)
                    
                    # History
                    gemini_history = []
                    for msg in st.session_state.messages[-6:]: # Lấy 6 tin gần nhất
                        if msg["role"] in ["user", "model"]: # Lọc role hợp lệ
                            gemini_history.append({"role": "user" if msg["role"]=="user" else "model", "parts": [str(msg["content"])]})

                    chat = model.start_chat(history=gemini_history)
                    response = chat.send_message(prompt)
                    raw_text = response.text
                    
                    # Xử lý MAP_CMD từ AI
                    map_cmd_match = re.search(r"MAP_CMD:\s*(.*?)\s*\|\s*(.*)", raw_text)
                    
                    if map_cmd_match:
                        origin_raw = map_cmd_match.group(1).strip()
                        dest_raw = map_cmd_match.group(2).strip()
                        
                        # Xử lý GPS
                        final_origin = st.session_state.user_location if (origin_raw == "CURRENT_LOC" and st.session_state.user_location) else origin_raw
                        if origin_raw == "CURRENT_LOC" and not st.session_state.user_location:
                            final_origin = "Ho Chi Minh City" # Fallback
                            response_text = "⚠️ Chưa lấy được GPS, tôi sẽ tính từ trung tâm TP.HCM.\n"

                        st.session_state.custom_route = {"origin": final_origin, "destination": dest_raw}
                        
                        # GỌI GOOGLE DIRECTIONS API (Backend) để lấy text chi tiết
                        directions_text, err = get_google_directions_text(final_origin, dest_raw, maps_key)
                        
                        clean_ai_text = raw_text.replace(map_cmd_match.group(0), "").strip()
                        
                        if directions_text:
                            response_text += f"{clean_ai_text}\n\n<div class='direction-box'><b>🗺️ Chi tiết lộ trình:</b><br>{directions_text.replace(chr(10), '<br>')}</div>"
                        else:
                            response_text += clean_ai_text
                    else:
                        response_text = raw_text

                except Exception as e:
                    response_text = f"⚠️ Lỗi AI: {e}"
            else:
                response_text = "Vui lòng nhập API Key để tôi có thể chỉ đường thông minh."

            # TTS Output
            msg_data = {"role": "assistant", "content": response_text}
            if enable_tts:
                # Chỉ đọc phần text, bỏ qua phần HTML hướng dẫn dài dòng để tránh đọc lâu
                text_to_read = re.sub(r"<div.*</div>", "Tôi đã tìm thấy lộ trình chi tiết bên dưới.", response_text, flags=re.DOTALL)
                audio_bytes = text_to_speech_stream(text_to_read)
                if audio_bytes: msg_data["audio"] = audio_bytes

            st.session_state.messages.append(msg_data)
            st.rerun()

    else: # Chế độ Tra cứu Tuyến (Giữ nguyên logic cũ)
        st.subheader("🔍 Tra cứu Tuyến Xe")
        search_q = st.text_input("Nhập số xe (VD: 152, 01)...")
        if search_q:
            found = next((b for b in BUS_DATA if b['id'] == search_q or b['id'] == search_q.upper()), None)
            if found:
                st.success(f"Tuyến {found['name']}")
                st.write(f"**Giá:** {found['price']} | **Giờ:** {found['time']}")
                st.write(f"**Lộ trình:** {', '.join(found['stops'])}")
                st.session_state.selected_route = found
                st.session_state.custom_route = None
            else:
                st.error("Không tìm thấy tuyến này.")

# --- 7. CỘT PHẢI: BẢN ĐỒ & TRẠNG THÁI ---
with col2:
    st.subheader("🗺️ Bản đồ & Lộ trình")
    
    # Ưu tiên hiển thị Route tùy chỉnh (A->B)
    if st.session_state.custom_route:
        r = st.session_state.custom_route
        st.markdown(f"**Từ:** `{r['origin']}` ➝ **Đến:** `{r['destination']}`")
        map_html = render_map_html(r['origin'], r['destination'], maps_key)
        components.html(map_html, height=450)
        
    # Hoặc hiển thị Route xe buýt cụ thể
    elif st.session_state.selected_route:
        bus = st.session_state.selected_route
        st.markdown(f"**Tuyến:** `{bus['name']}`")
        # Với tuyến xe, ta vẽ từ điểm đầu đến điểm cuối
        map_html = render_map_html(bus['stops'][0], bus['stops'][-1], maps_key)
        components.html(map_html, height=450)
    
    else:
        st.info("👋 Hãy chat để tìm đường hoặc tra cứu tuyến xe.")
        st.markdown("""
        <div style="text-align:center; padding: 40px; color: #10b981; border: 2px dashed #10b981; border-radius: 10px;">
            <h1 style="font-size: 60px;">🚌</h1>
            <h3>VnBus Green AI</h3>
        </div>
        """, unsafe_allow_html=True)
