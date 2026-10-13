import os
import re
import json
from io import BytesIO
from PIL import Image
import pandas as pd
import streamlit as st
import google.generativeai as genai

# Cấu hình giao diện Streamlit
st.set_page_config(
    page_title="Quét Phiếu Nhập Kho",
    page_icon="📦",
    layout="centered"
)

st.title("📦 Quét Phiếu Nhập Kho Sang Excel")
st.caption("Ứng dụng tự động đọc chứng từ, phiếu kho và xuất bảng dữ liệu Excel")

# --- QUẢN LÝ API KEY ---
# Tìm API Key từ st.secrets hoặc biến môi trường, nếu chưa có thì cho nhập ở Sidebar
default_api_key = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        default_api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if not default_api_key:
    default_api_key = os.environ.get("GEMINI_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Cấu hình")
    api_key = st.text_input(
        "Gemini API Key:",
        value=default_api_key,
        type="password",
        help="Lấy API Key miễn phí tại https://aistudio.google.com"
    )
    st.markdown("---")
    st.markdown("""
    **Hướng dẫn nhanh:**
    1. Nhập **Gemini API Key**.
    2. Chụp ảnh hoặc tải ảnh phiếu kho.
    3. Bấm **Bắt đầu quét**.
    4. Kiểm tra, sửa bảng và copy/tải file Excel.
    """)

# --- KHU VỰC TẢI / CHỤP ẢNH ---
tab_camera, tab_upload = st.tabs(["📸 Chụp ảnh bằng camera", "📁 Tải ảnh từ máy"])

image_file = None
with tab_camera:
    cam_file = st.camera_input("Chụp ảnh phiếu nhập kho")
    if cam_file:
        image_file = cam_file

with tab_upload:
    up_file = st.file_uploader("Chọn ảnh phiếu kho (JPG, PNG)", type=["jpg", "jpeg", "png"])
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
    
    # Sử dụng gemini-1.5-flash chuẩn hoá tương thích cao nhất
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content([pil_image, prompt])
    except Exception:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content([pil_image, prompt])
    
    text = response.text.strip()
    # Loại bỏ code block markdown nếu có
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())

# --- XỬ LÝ VÀ HIỂN THỊ DỮ LIỆU ---
if image_file:
    img = Image.open(image_file)
    st.image(img, caption="Ảnh phiếu cần quét", use_container_width=True)

    if st.button("🚀 Bắt đầu quét dữ liệu", type="primary", use_container_width=True):
        if not api_key:
            st.error("⚠️ Vui lòng nhập Gemini API Key ở menu Cấu hình bên trái trước khi quét.")
        else:
            with st.spinner("AI đang nhận diện chữ và cấu trúc bảng..."):
                try:
                    result = extract_receipt_with_gemini(img, api_key)
                    st.session_state["receipt_data"] = result
                    st.success("✅ Đã trích xuất dữ liệu thành công!")
                except Exception as e:
                    st.error(f"❌ Xảy ra lỗi khi đọc ảnh: {str(e)}")

if "receipt_data" in st.session_state:
    data = st.session_state["receipt_data"]
    items = data.get("danh_sach_hang", [])

    st.markdown("---")
    st.subheader("📑 Thông tin chung")
    c1, c2, c3 = st.columns(3)
    so_phieu = c1.text_input("Số phiếu:", value=data.get("so_phieu", ""))
    ngay_nhap = c2.text_input("Ngày nhập:", value=data.get("ngay_nhap", ""))
    nha_cung_cap = c3.text_input("Nhà cung cấp:", value=data.get("nha_cung_cap", ""))

    st.subheader("📋 Bảng chi tiết mặt hàng (Có thể bấm trực tiếp vào ô để sửa)")
    df = pd.DataFrame(items)
    
    # Cho phép chỉnh sửa trực tiếp trên bảng Streamlit
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True
    )

    st.markdown("---")
    st.subheader("📤 Xuất & Chia sẻ dữ liệu")

    col_btn1, col_btn2 = st.columns(2)

    # 1. Tạo dữ liệu file Excel
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        edited_df.to_excel(writer, index=False, sheet_name="PhieuNhapKho")
    excel_bytes = excel_buffer.getvalue()
    file_name = f"phieu_nhap_{so_phieu if so_phieu else 'kho'}.xlsx"

    # Nút Tải file truyền thống
    col_btn1.download_button(
        label="📥 Tải file Excel (.xlsx)",
        data=excel_bytes,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    # 2. Hỗ trợ copy thẳng vào Excel (TSV format)
    tsv_data = edited_df.to_csv(sep="\t", index=False)
    with col_btn2:
        with st.popover("📋 Copy nhanh bảng", use_container_width=True):
            st.caption("Bấm copy rồi dán (Ctrl+V) thẳng vào Excel:")
            st.code(tsv_data, language="text")

    # 3. NÚT CHIA SẺ TRỰC TIẾP QUA ZALO / MOBILE APPS
    import base64
    b64_excel = base64.b64encode(excel_bytes).decode('utf-8')
    
    share_component = f"""
    <div style="margin-top: 10px;">
        <button id="shareBtn" style="
            width: 100%;
            background-color: #0068FF;
            color: white;
            border: none;
            padding: 12px 20px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
            💬 Chia sẻ file qua Zalo / Ứng dụng
        </button>
        <p id="msg" style="text-align: center; color: gray; font-size: 13px; margin-top: 6px;"></p>
    </div>

    <script>
    document.getElementById("shareBtn").addEventListener("click", async () => {{
        const b64Data = "{b64_excel}";
        const fileName = "{file_name}";
        
        try {{
            // Chuyển base64 thành Blob File
            const byteCharacters = atob(b64Data);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {{
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }}
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], {{ type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }});
            const file = new File([blob], fileName, {{ type: blob.type }});

            // Kiểm tra hỗ trợ Web Share API (trên điện thoại iOS/Android)
            if (navigator.canShare && navigator.canShare({{ files: [file] }})) {{
                await navigator.share({{
                    files: [file],
                    title: "Phiếu nhập kho: " + "{so_phieu if so_phieu else ''}",
                    text: "Gửi bạn file Excel phiếu nhập kho đã quét."
                }});
            }} else {{
                // Nếu trên máy tính không hỗ trợ share file trực tiếp, tự động tải file xuống
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = fileName;
                a.click();
                document.getElementById("msg").innerText = "Đã tải file xuống máy của bạn.";
            }}
        }} catch (err) {{
            if (err.name !== "AbortError") {{
                document.getElementById("msg").innerText = "Vui lòng dùng nút Tải file ở trên.";
            }}
        }}
    }});
    </script>
    """
    st.components.v1.html(share_component, height=80)
