import os
import re
import json
import base64
from io import BytesIO
from PIL import Image
import pandas as pd
import streamlit as st
import google.generativeai as genai

# --- CẤU HÌNH GIAO DIỆN STREAMLIT ---
st.set_page_config(
    page_title="Đọc ảnh ➜ Excel | WPRO.vn",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- TÙY BIẾN CSS HIỆN ĐẠI (ẨN HOÀN TOÀN SIDEBAR & HEADER MẶC ĐỊNH) ---
st.markdown("""
<style>
    /* 1. Ẩn triệt để Sidebar và nút điều khiển Sidebar */
    [data-testid="stSidebar"], 
    [data-testid="collapsedControl"],
    section[data-testid="stSidebar"] {
        display: none !important;
    }

    /* 2. Ẩn Header mặc định của Streamlit (Menu, GitHub icon, Deploy button) */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    footer {
        display: none !important;
    }
    #MainMenu {
        display: none !important;
    }

    /* 3. Tối ưu không gian hiển thị trên mobile và desktop */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 650px !important;
    }

    /* 4. Thiết kế Tab chuyển đổi (Chụp ảnh / Tải ảnh) dạng thẻ tròn hiện đại */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f1f5f9;
        padding: 5px;
        border-radius: 12px;
        border-bottom: none !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        color: #64748b !important;
        border: none !important;
        background-color: transparent !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #0068ff !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08) !important;
    }

    /* 5. Nút bấm chính (Call to Action) */
    button[kind="primary"] {
        background: linear-gradient(135deg, #0068FF 0%, #0050cc 100%) !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 20px !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        box-shadow: 0 4px 12px rgba(0, 104, 255, 0.25) !important;
        transition: all 0.2s ease-in-out !important;
    }
    button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(0, 104, 255, 0.35) !important;
    }

    /* 6. Thẻ chứa thông tin chung */
    .meta-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER APP HIỆN ĐẠI & THƯƠNG HIỆU WPRO.VN ---
st.markdown("""
<div style="text-align: center; margin-bottom: 24px;">
    <div style="
        display: inline-flex; 
        align-items: center; 
        justify-content: center; 
        width: 58px; 
        height: 58px; 
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); 
        border-radius: 16px; 
        box-shadow: 0 6px 16px rgba(2, 132, 199, 0.28); 
        margin-bottom: 12px;
    ">
        <span style="font-size: 28px;">📊</span>
    </div>
    <h2 style="font-size: 24px; font-weight: 800; color: #0f172a; margin: 0 0 6px 0; letter-spacing: -0.5px;">
        Đọc ảnh ➜ Excel
    </h2>
    <div style="display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 6px;">
        <span style="font-size: 13px; color: #64748b;">Giải pháp thông minh bởi</span>
        <a href="https://wpro.vn" target="_blank" style="
            display: inline-flex;
            align-items: center;
            gap: 4px;
            background: #e0f2fe;
            color: #0284c7;
            font-size: 12px;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 20px;
            text-decoration: none;
            transition: all 0.2s ease;
        ">
            🌐 WPRO.vn ↗
        </a>
    </div>
    <p style="font-size: 13px; color: #94a3b8; margin: 0;">Tự động nhận diện chữ, xuất bảng tính & gửi nhanh qua Zalo</p>
</div>
""", unsafe_allow_html=True)

# --- QUẢN LÝ API KEY TỰ ĐỘNG (KHÔNG DÙNG SIDEBAR) ---
api_key = ""
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
elif "GEMINI_API_KEY" in os.environ:
    api_key = os.environ["GEMINI_API_KEY"]

# Nếu chưa lưu vào Secrets (khi chạy ở máy tính lạ), hiển thị ô nhập gọn gàng không chiếm diện tích
if not api_key:
    with st.expander("🔑 Cài đặt API Key (Chỉ cần nhập nếu chưa lưu Secrets)", expanded=True):
        api_key = st.text_input("Nhập Gemini API Key:", type="password", placeholder="AIzaSy...")

# --- KHU VỰC CHỤP HOẶC TẢI ẢNH ---
tab_camera, tab_upload = st.tabs(["📸 Chụp ảnh phiếu", "📁 Tải ảnh từ thư viện"])

image_file = None
with tab_camera:
    cam_file = st.camera_input("Chụp ảnh phiếu kho")
    if cam_file:
        image_file = cam_file

with tab_upload:
    up_file = st.file_uploader("Chọn ảnh phiếu kho", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
    if up_file:
        image_file = up_file

# --- HÀM XỬ LÝ AI ---
def extract_receipt_with_gemini(pil_image: Image.Image, key: str) -> dict:
    clean_key = str(key).strip().strip('"').strip("'")
    genai.configure(api_key=clean_key)
    
    prompt = """
    Bạn là chuyên gia trích xuất dữ liệu chứng từ, hóa đơn và phiếu nhập kho tiếng Việt.
    Hãy phân tích kỹ hình ảnh và trích xuất dữ liệu thành định dạng JSON đúng cấu trúc sau:
    {
        "so_phieu": "Số phiếu nếu có",
        "ngay_nhap": "Ngày/tháng/năm nếu có",
        "nha_cung_cap": "Tên nhà cung cấp / đơn vị giao hàng nếu có",
        "danh_sach_hang": [
            {
                "STT": 1,
                "Mã hàng": "Mã sản phẩm nếu có",
                "Tên hàng": "Tên sản phẩm, quy cách",
                "ĐVT": "Cái / Kg / Hộp ...",
                "Số lượng": 10.0,
                "Đơn giá": 50000.0,
                "Thành tiền": 500000.0,
                "Ghi chú": ""
            }
        ]
    }
    Quy tắc quan trọng:
    - Bắt buộc trả về đúng định dạng JSON hợp lệ.
    - Cột Số lượng, Đơn giá, Thành tiền phải là số (number), không chứa chữ cái hay ký tự tiền tệ.
    - Nếu hình ảnh viết tắt hoặc chữ mờ, cố gắng suy luận hợp lý nhất theo ngữ cảnh hàng hóa.
    - Nếu Thành tiền để trống, hãy tự tính: Số lượng * Đơn giá.
    """
    
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content([pil_image, prompt])
    except Exception:
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content([pil_image, prompt])
    
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())

# --- XỬ LÝ QUÉT ẢNH ---
if image_file:
    img = Image.open(image_file)
    st.image(img, caption="Ảnh phiếu đã chụp/chọn", use_container_width=True)

    if st.button("🚀 Bắt đầu quét dữ liệu", type="primary", use_container_width=True):
        if not api_key:
            st.error("⚠️ Vui lòng cung cấp Gemini API Key để quét.")
        else:
            with st.spinner("AI đang nhận diện chữ và phân tích bảng..."):
                try:
                    result = extract_receipt_with_gemini(img, api_key)
                    st.session_state["receipt_data"] = result
                    st.success("✅ Đã trích xuất thành công! Kiểm tra bảng bên dưới.")
                except Exception as e:
                    st.error(f"❌ Xảy ra lỗi khi đọc ảnh: {str(e)}")

# --- HIỂN THỊ KẾT QUẢ ---
if "receipt_data" in st.session_state:
    data = st.session_state["receipt_data"]
    items = data.get("danh_sach_hang", [])

    st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
    
    st.markdown("#### 📑 Thông tin phiếu")
    c1, c2, c3 = st.columns(3)
    so_phieu = c1.text_input("Số phiếu:", value=data.get("so_phieu", ""), key="inp_so_phieu")
    ngay_nhap = c2.text_input("Ngày:", value=data.get("ngay_nhap", ""), key="inp_ngay_nhap")
    nha_cung_cap = c3.text_input("Nhà cung cấp:", value=data.get("nha_cung_cap", ""), key="inp_ncc")

    st.markdown("#### 📋 Chi tiết mặt hàng *(chạm vào ô để sửa)*")
    df = pd.DataFrame(items)
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True
    )

    st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
    st.markdown("#### 📤 Xuất & Chia sẻ")

    # Tạo file Excel
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        edited_df.to_excel(writer, index=False, sheet_name="PhieuNhapKho")
    excel_bytes = excel_buffer.getvalue()
    file_name = f"phieu_nhap_{so_phieu if so_phieu else 'kho'}.xlsx"
    b64_excel = base64.b64encode(excel_bytes).decode('utf-8')

    # NÚT CHIA SẺ QUA ZALO / MOBILE APPS
    share_component = f"""
    <div style="margin-bottom: 12px;">
        <button id="shareBtn" style="
            width: 100%;
            background: linear-gradient(135deg, #0068FF 0%, #004ec2 100%);
            color: white;
            border: none;
            padding: 13px 20px;
            font-size: 16px;
            font-weight: 700;
            border-radius: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            box-shadow: 0 4px 12px rgba(0, 104, 255, 0.3);
            transition: all 0.2s ease;
        ">
            💬 Gửi file qua Zalo / Tin nhắn
        </button>
        <p id="msg" style="text-align: center; color: #64748b; font-size: 13px; margin-top: 6px;"></p>
    </div>

    <script>
    document.getElementById("shareBtn").addEventListener("click", async () => {{
        const b64Data = "{b64_excel}";
        const fileName = "{file_name}";
        
        try {{
            const byteCharacters = atob(b64Data);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {{
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }}
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], {{ type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }});
            const file = new File([blob], fileName, {{ type: blob.type }});

            if (navigator.canShare && navigator.canShare({{ files: [file] }})) {{
                await navigator.share({{
                    files: [file],
                    title: "Phiếu nhập kho: " + "{so_phieu if so_phieu else ''}",
                    text: "Gửi bạn file Excel phiếu nhập kho đã quét."
                }});
            }} else {{
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = fileName;
                a.click();
                document.getElementById("msg").innerText = "Đã tải file xuống máy của bạn.";
            }}
        }} catch (err) {{
            if (err.name !== "AbortError") {{
                document.getElementById("msg").innerText = "Vui lòng dùng nút Tải file bên dưới.";
            }}
        }}
    }});
    </script>
    """
    st.components.v1.html(share_component, height=75)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 Tải file Excel (.xlsx)",
            data=excel_bytes,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with col2:
        tsv_data = edited_df.to_csv(sep="\t", index=False)
        with st.popover("📋 Copy nhanh bảng", use_container_width=True):
            st.caption("Copy và dán (Ctrl+V) thẳng vào Excel:")
            st.code(tsv_data, language="text")

# --- FOOTER THƯƠNG HIỆU WPRO.VN ---
st.markdown("""
<div style="
    text-align: center; 
    margin-top: 45px; 
    padding-top: 20px; 
    border-top: 1px solid #e2e8f0; 
    font-size: 13px; 
    color: #94a3b8;
">
    © Bản quyền thuộc về <a href="https://wpro.vn" target="_blank" style="color: #0284c7; font-weight: 700; text-decoration: none;">WPRO.vn</a> – Giải Pháp Quản Trị Kho & Bán Hàng
</div>
""", unsafe_allow_html=True)
