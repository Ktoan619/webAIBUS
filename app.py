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

# --- 1. CẤU HÌNH TRANG & CSS ---
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
    
    .direction-box {
        background-color: #d1fae5; border-left: 5px solid #059669;
        padding: 15px; border-radius: 5px; margin-top: 10px;
    }
    .price-tag {
        background-color: #f59e0b; color: white !important; 
        padding: 2px 6px; border-radius: 4px; font-size: 0.9em; font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CÁC HÀM XỬ LÝ ---

def text_to_speech_stream(text):
    """Chuyển văn bản thành giọng nói (gTTS)"""
    try:
        clean_text = re.sub(r'[*_#<>]', '', text)
        tts = gTTS(text=clean_text, lang='vi')
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        return audio_fp
    except: return None

def transcribe_audio_with_gemini(audio_file, api_key):
    """Dùng Gemini để chuyển giọng nói thành văn bản"""
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        # SỬA LỖI: Chuyển sang model 2.0-flash-exp để đồng bộ và ổn định hơn
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        
        # Đọc dữ liệu audio
        audio_bytes = audio_file.read()
        
        prompt = "Hãy chép lại chính xác những gì người dùng nói trong đoạn ghi âm này bằng tiếng Việt. Chỉ trả về nội dung văn bản, không thêm lời dẫn."
        
        response = model.generate_content([
            prompt,
            {"mime_type": "audio/wav", "data": audio_bytes}
        ])
        return response.text.strip()
    except Exception as e:
        st.error(f"Lỗi nhận diện giọng nói: {e}")
        return None

def get_google_directions_text(origin, destination, api_key):
    """Gọi Google Directions API"""
    if not api_key: return None, None, None
    try:
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": origin, "destination": destination,
            "mode": "transit", "transit_mode": "bus",
            "language": "vi", "key": api_key
        }
        resp = requests.get(url, params=params).json()
        if resp["status"] != "OK": return None, f"Lỗi Google Maps: {resp['status']}", None
        
        leg = resp["routes"][0]["legs"][0]
        duration = leg["duration"]["text"]
        distance = leg["distance"]["text"]
        
        steps_info = []
        voice_sentences = [f"Tìm thấy lộ trình dài {distance}, mất khoảng {duration}."]
        summary = f"🚌 <b>Lộ trình:</b> {distance} (khoảng {duration})."
        
        for step in leg["steps"]:
            instruction = re.sub('<[^<]+?>', '', step["html_instructions"])
            if step["travel_mode"] == "TRANSIT":
                td = step["transit_details"]
                bus_line = td["line"].get("short_name", "Bus")
                headsign = td["headsign"]
                dep_time = td.get("departure_time", {}).get("text", "sắp đến")
                
                # Tra cứu giá vé
                found_bus = next((b for b in BUS_DATA if b['id'] == bus_line), None)
                bus_price = f"<span class='price-tag'>{found_bus['price']}</span>" if found_bus else ""
                price_voice = f"Giá vé {found_bus['price'].replace('.', '').replace('đ', ' đồng')}." if found_bus else ""
                
                steps_info.append(f"""
                <div style="margin-bottom:8px;">
                    🚍 <b>Bắt xe {bus_line}</b> {bus_price}<br>
                    <small>Hướng: {headsign} • Xe đến: <b>{dep_time}</b></small><br>
                    <i style="color:#444;">{instruction}</i>
                </div>
                """)
                voice_sentences.append(f"Đón xe số {bus_line} hướng về {headsign}. {price_voice} Xe đến lúc {dep_time}.")
            elif step["travel_mode"] == "WALKING":
                steps_info.append(f"🚶 {instruction}")
                voice_sentences.append(f"Đi bộ: {instruction}.")
        
        full_html = summary + "<br><hr>" + "".join(steps_info)
        return full_html, None, " ".join(voice_sentences)
    except Exception as e:
        return None, str(e), None

# --- 3. QUẢN LÝ TRẠNG THÁI ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Xin chào! Bạn muốn đi đâu? (Nhấn nút 🎙️ để nói)"}]
if "selected_route" not in st.session_state: st.session_state.selected_route = None
if "custom_route" not in st.session_state: st.session_state.custom_route = None
if "user_location" not in st.session_state: st.session_state.user_location = None

# --- 4. GIAO DIỆN SIDEBAR ---
with st.sidebar:
    st.title("🌿 VnBus Pro")
    st.markdown("---")
    maps_key = st.secrets.get("GOOGLE_MAPS_KEY", "") or st.text_input("🔑 Google Maps Key", type="password")
    gemini_key = st.secrets.get("GEMINI_KEY", "") or st.text_input("✨ Gemini API Key", type="password")
    
    st.markdown("---")
    if st.checkbox("Sử dụng Vị trí hiện tại"):
        loc = get_geolocation()
        if loc:
            lat, lng = loc['coords']['latitude'], loc['coords']['longitude']
            st.session_state.user_location = f"{lat},{lng}"
            st.success(f"📍 Đã định vị: {lat:.4f}, {lng:.4f}")
        else:
            st.warning("Đang chờ tín hiệu GPS...")

    st.markdown("---")
    enable_tts = st.checkbox("🔊 Đọc to câu trả lời", value=True)
    mode = st.radio("Chế độ:", ["Chat & Chỉ đường 🤖", "Tra cứu Tuyến 🚌"])

# --- 5. RENDER MAP ---
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
        chat_container = st.container(height=400)
        
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"], unsafe_allow_html=True)
                if msg.get("audio"): st.audio(msg["audio"], format="audio/mp3")

        # --- KHU VỰC NHẬP LIỆU (TEXT + VOICE) ---
        # 1. Nhập văn bản
        text_prompt = st.chat_input("Nhập nơi muốn đến...")
        
        # 2. Nhập giọng nói (Widget mới)
        audio_prompt = st.audio_input("🎙️ Nhấn để nói", label_visibility="collapsed")
        
        final_prompt = None
        
        # Ưu tiên xử lý Audio nếu có
        if audio_prompt:
            if not gemini_key:
                st.error("Vui lòng nhập Gemini Key để dùng tính năng giọng nói.")
            else:
                with st.spinner("Đang nghe và dịch..."):
                    transcribed_text = transcribe_audio_with_gemini(audio_prompt, gemini_key)
                    if transcribed_text:
                        final_prompt = transcribed_text
        # Nếu không có audio mới dùng text
        elif text_prompt:
            final_prompt = text_prompt

        # --- XỬ LÝ PROMPT ---
        if final_prompt:
            st.session_state.messages.append({"role": "user", "content": final_prompt})
            with chat_container:
                with st.chat_message("user"): st.write(final_prompt)

            response_text = ""
            voice_text_response = ""
            
            if gemini_key:
                try:
                    genai.configure(api_key=gemini_key)
                    sys_prompt = get_full_system_instruction() + "\n\nQUAN TRỌNG: Nếu người dùng nói 'từ đây', 'vị trí của tôi', hãy trả về MAP_CMD với điểm đi là 'CURRENT_LOC'."
                    model = genai.GenerativeModel('gemini-2.0-flash-exp', system_instruction=sys_prompt)
                    
                    gemini_history = [{"role": "user" if m["role"]=="user" else "model", "parts": [str(m["content"])]} for m in st.session_state.messages[-6:]]
                    
                    chat = model.start_chat(history=gemini_history)
                    response = chat.send_message(final_prompt)
                    raw_text = response.text
                    
                    map_cmd_match = re.search(r"MAP_CMD:\s*(.*?)\s*\|\s*(.*)", raw_text)
                    
                    if map_cmd_match:
                        origin_raw, dest_raw = map_cmd_match.group(1).strip(), map_cmd_match.group(2).strip()
                        final_origin = st.session_state.user_location if (origin_raw == "CURRENT_LOC" and st.session_state.user_location) else origin_raw
                        if origin_raw == "CURRENT_LOC" and not st.session_state.user_location:
                            final_origin, response_text = "Ho Chi Minh City", "⚠️ Chưa lấy được GPS, tính từ trung tâm.\n"

                        st.session_state.custom_route = {"origin": final_origin, "destination": dest_raw}
                        
                        directions_html, err, voice_optimized = get_google_directions_text(final_origin, dest_raw, maps_key)
                        clean_ai_text = raw_text.replace(map_cmd_match.group(0), "").strip()
                        
                        if directions_html:
                            response_text += f"{clean_ai_text}\n\n<div class='direction-box'>{directions_html}</div>"
                            voice_text_response = f"{clean_ai_text}. {voice_optimized}"
                        else:
                            response_text += clean_ai_text
                            voice_text_response = clean_ai_text
                    else:
                        response_text, voice_text_response = raw_text, raw_text

                except Exception as e:
                    response_text = f"⚠️ Lỗi AI: {e}"
            else:
                response_text = "Vui lòng nhập API Key."

            msg_data = {"role": "assistant", "content": response_text}
            if enable_tts:
                audio_bytes = text_to_speech_stream(voice_text_response or re.sub(r"<[^>]+>", "", response_text))
                if audio_bytes: msg_data["audio"] = audio_bytes

            st.session_state.messages.append(msg_data)
            st.rerun()

    else: # Chế độ Tra cứu
        st.subheader("🔍 Tra cứu Tuyến Xe")
        search_q = st.text_input("Nhập số xe (VD: 152)...")
        if search_q:
            found = next((b for b in BUS_DATA if b['id'] == search_q or b['id'] == search_q.upper()), None)
            if found:
                st.success(f"Tuyến {found['name']}")
                st.write(f"**Giá:** {found['price']} | **Giờ:** {found['time']}")
                st.write(f"**Lộ trình:** {', '.join(found['stops'])}")
                st.session_state.selected_route = found
                st.session_state.custom_route = None
            else: st.error("Không tìm thấy tuyến này.")

# --- 7. CỘT PHẢI ---
with col2:
    st.subheader("🗺️ Bản đồ & Lộ trình")
    if st.session_state.custom_route:
        r = st.session_state.custom_route
        st.markdown(f"**Từ:** `{r['origin']}` ➝ **Đến:** `{r['destination']}`")
        components.html(render_map_html(r['origin'], r['destination'], maps_key), height=450)
    elif st.session_state.selected_route:
        bus = st.session_state.selected_route
        st.markdown(f"**Tuyến:** `{bus['name']}`")
        components.html(render_map_html(bus['stops'][0], bus['stops'][-1], maps_key), height=450)
    else:
        st.info("👋 Hãy chat để tìm đường hoặc tra cứu tuyến xe.")
        st.markdown("""<div style="text-align:center; padding: 40px; color: #10b981; border: 2px dashed #10b981; border-radius: 10px;"><h1 style="font-size: 60px;">🚌</h1><h3>VnBus Green AI</h3></div>""", unsafe_allow_html=True)
