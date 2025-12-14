import streamlit as st
import google.generativeai as genai
import streamlit.components.v1 as components

# --- 1. CẤU HÌNH TRANG & CSS XANH LÁ ---
st.set_page_config(
    page_title="VnBus Green AI",
    page_icon="🍃",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS cho màu xanh lá chủ đạo
st.markdown("""
<style>
    /* Màu chủ đạo xanh lá */
    .stApp {
        background-color: #f0fdf4;
    }
    .stButton>button {
        background-color: #10b981;
        color: white;
        border-radius: 10px;
        border: none;
        font-weight: bold;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #059669;
        color: white;
    }
    .stTextInput>div>div>input {
        border-radius: 10px;
        border: 1px solid #10b981;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    h1, h2, h3 {
        color: #064e3b;
    }
    /* Ẩn footer mặc định */
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 2. DỮ LIỆU GIẢ LẬP ---
BUS_DATA = [
    {
        "id": "VIN01",
        "name": "VinBus 01: Vinhomes Grand Park - Emart",
        "price": "7.000đ",
        "time": "05:00 - 22:00",
        "stops": ["Vinhomes Grand Park", "Lê Văn Việt", "Ngã 4 Thủ Đức", "Phạm Văn Đồng", "Emart Gò Vấp"],
        "color": "#10b981"
    },
    {
        "id": "152",
        "name": "Tuyến 152: Trung Sơn - Sân Bay TSN",
        "price": "5.000đ",
        "time": "05:15 - 19:00",
        "stops": ["KDC Trung Sơn", "Trần Hưng Đạo", "Bến Thành", "Nam Kỳ Khởi Nghĩa", "Sân bay Tân Sơn Nhất"],
        "color": "#34d399"
    },
    {
        "id": "01",
        "name": "Tuyến 01: Bến Thành - Chợ Lớn",
        "price": "6.000đ",
        "time": "05:00 - 20:30",
        "stops": ["Bến Thành", "Trần Hưng Đạo", "Nguyễn Tri Phương", "Hùng Vương", "Chợ Lớn"],
        "color": "#059669"
    }
]

# --- 3. STATE MANAGEMENT ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Xin chào! Tôi là Trợ lý VnBus Green. Bạn muốn di chuyển xanh đến đâu hôm nay? 🌱"}
    ]
if "selected_route" not in st.session_state:
    st.session_state.selected_route = None
if "custom_route" not in st.session_state:
    st.session_state.custom_route = None

# --- 4. HÀM XỬ LÝ HTML MAP ---
def render_map_html(route_data, api_key=None, is_custom=False):
    """
    Render map: Ưu tiên dùng Google Maps Embed nếu có Key.
    Nếu không, fallback về giao diện HTML mô phỏng (Simulation Mode).
    """
    
    # CASE A: CÓ API KEY (GOOGLE MAPS REAL)
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
            
        return f"""
            <div style="width:100%; height:500px; border-radius:15px; overflow:hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                <iframe width="100%" height="100%" frameborder="0" style="border:0" 
                src="{src}" allowfullscreen></iframe>
            </div>
        """

    # CASE B: KHÔNG CÓ KEY (CHẾ ĐỘ MÔ PHỎNG - SIMULATION MODE)
    stops = route_data['stops'] if not is_custom else [route_data['origin'], "Trạm trung chuyển", "Trạm kết nối", route_data['destination']]
    color = route_data.get('color', '#8b5cf6') if not is_custom else '#8b5cf6'
    
    timeline_html = ""
    for idx, stop in enumerate(stops):
        bg_color = color if idx == 0 else (color if idx == len(stops)-1 else '#cbd5e1')
        timeline_html += f"""
        <div style="display:flex; align-items:start; margin-bottom: 20px; position:relative;">
            <div style="width:30px; height:30px; background-color:{bg_color}; border-radius:50%; border:3px solid white; box-shadow:0 2px 4px rgba(0,0,0,0.1); z-index:10; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; font-size:12px;">{idx+1}</div>
            <div style="margin-left:15px; background:white; padding:10px 15px; border-radius:10px; border:1px solid #e2e8f0; width:100%;">
                <div style="font-weight:bold; color:#334155;">{stop}</div>
            </div>
            {'<div style="position:absolute; left:14px; top:30px; bottom:-25px; width:2px; background-color:#e2e8f0; z-index:0;"></div>' if idx != len(stops)-1 else ''}
        </div>
        """

    return f"""
        <div style="background-color:#f8fafc; padding:20px; border-radius:15px; height:500px; overflow-y:auto; border:1px solid #e2e8f0;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; padding-bottom:10px; border-bottom:1px solid #e2e8f0;">
                <span style="font-weight:bold; color:#0f172a;">🗺️ Lộ trình mô phỏng</span>
                <span style="font-size:10px; background:#dcfce7; color:#166534; padding:2px 8px; border-radius:10px; border:1px solid #bbf7d0;">Simulation Mode</span>
            </div>
            {timeline_html}
            <div style="text-align:center; margin-top:20px; font-size:12px; color:#94a3b8;">
                ⚠️ Nhập API Key để xem bản đồ thực tế.
            </div>
        </div>
    """

# --- 5. GIAO DIỆN SIDEBAR & SECRETS ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3448/3448339.png", width=50)
    st.header("Cấu hình & Bảo mật")
    
    # --- LOGIC ĐỌC SECRET TỰ ĐỘNG ---
    # Google Maps Key
    if "GOOGLE_MAPS_KEY" in st.secrets:
        maps_key = st.secrets["GOOGLE_MAPS_KEY"]
        st.success("✅ Đã nạp Maps Key từ hệ thống")
    else:
        maps_key = st.text_input("Google Maps Key", type="password", placeholder="AIzaSy...")

    # Gemini Key
    if "GEMINI_KEY" in st.secrets:
        gemini_key = st.secrets["GEMINI_KEY"]
        st.success("✅ Đã nạp Gemini Key từ hệ thống")
    else:
        gemini_key = st.text_input("Gemini API Key", type="password", placeholder="AI Key...")
    
    if not maps_key:
        st.caption("ℹ️ Chế độ mô phỏng đang bật.")
    
    st.markdown("---")
    mode = st.radio("Chế độ:", ["Trợ lý Chat 🤖", "Tìm đường 📍"])

# --- 6. LOGIC CHÍNH ---
col1, col2 = st.columns([1, 1.3])

with col1:
    if mode == "Trợ lý Chat 🤖":
        st.subheader("💬 Trợ lý VnBus")
        
        chat_container = st.container(height=400)
        with chat_container:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

        if prompt := st.chat_input("Nhập tuyến xe (VD: 152) hoặc hỏi AI..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"):
                    st.write(prompt)

            # Logic tìm kiếm
            response_text = ""
            found_bus = next((b for b in BUS_DATA if b['id'] in prompt or b['id'] in prompt.upper()), None)
            
            if found_bus:
                st.session_state.selected_route = found_bus
                st.session_state.custom_route = None
                response_text = f"Đã tìm thấy **{found_bus['name']}**. Giá vé: {found_bus['price']}."
            elif gemini_key:
                try:
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel('gemini-2.0-flash-exp')
                    response = model.generate_content(f"Bạn là trợ lý xe buýt. Người dùng hỏi: '{prompt}'. Hãy trả lời ngắn gọn, vui vẻ.")
                    response_text = response.text
                except Exception as e:
                    response_text = f"Lỗi AI: {str(e)}"
            else:
                response_text = "Tôi chưa tìm thấy tuyến xe này. Hãy nhập số xe (VD: 152) hoặc nhập API Key để tôi hỏi AI."

            st.session_state.messages.append({"role": "assistant", "content": response_text})
            with chat_container:
                with st.chat_message("assistant"):
                    st.write(response_text)
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
                    "origin": origin,
                    "destination": destination,
                    "stops": [],
                    "duration": "25 phút",
                    "distance": "5.2 km"
                }
                st.success(f"Đã tìm thấy lộ trình từ {origin} đến {destination}")
                st.rerun()

# Cột Phải: Map
with col2:
    st.subheader("🗺️ Bản đồ trực quan")
    
    target_data = None
    is_custom = False
    
    if st.session_state.custom_route:
        target_data = st.session_state.custom_route
        is_custom = True
    elif st.session_state.selected_route:
        target_data = st.session_state.selected_route
        is_custom = False
        
    if target_data:
        map_html = render_map_html(target_data, api_key=maps_key, is_custom=is_custom)
        components.html(map_html, height=520, scrolling=False)
        
        if not is_custom:
            c1, c2 = st.columns(2)
            c1.info(f"💰 Giá vé: {target_data['price']}")
            c2.warning(f"⏰ Thời gian: {target_data['time']}")
            
            if gemini_key:
                if st.button("✨ Hỏi AI về địa điểm vui chơi"):
                    with st.spinner("AI đang phân tích..."):
                        try:
                            genai.configure(api_key=gemini_key)
                            model = genai.GenerativeModel('gemini-2.0-flash-exp')
                            stops_str = ", ".join(target_data['stops'])
                            res = model.generate_content(f"Tuyến xe buýt đi qua: {stops_str}. Gợi ý 3 địa điểm ăn uống vui chơi gần các trạm này. Ngắn gọn, dùng emoji.")
                            st.write(res.text)
                        except:
                            st.error("Lỗi kết nối AI.")
    else:
        st.markdown("""
        <div style="background:#f1f5f9; height:500px; border-radius:15px; display:flex; align-items:center; justify-content:center; flex-direction:column; color:#64748b;">
            <div style="font-size:50px;">🍃</div>
            <h3>Chưa có lộ trình</h3>
            <p>Hãy chọn tuyến xe hoặc nhập điểm đi/đến</p>
        </div>
        """, unsafe_allow_html=True)
