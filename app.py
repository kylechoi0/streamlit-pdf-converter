import json
import streamlit as st
import pdfplumber
import asyncio
import aiohttp
from io import BytesIO

API_URL = "https://api-mir.52g.ai/v1/chat-messages"
API_KEY = "app-uCvdsndj2nbDbnUtXaBwtwl0"

st.set_page_config(page_title="PDF to Markdown Converter", layout="wide")

# 스타일 설정
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
    }
    .output-area {
        background-color: #f0f2f6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-top: 1rem;
    }
    .tooltip {
        position: relative;
        display: inline-block;
        cursor: help;
    }
    .tooltip .tooltiptext {
        visibility: hidden;
        width: 200px;
        background-color: #555;
        color: #fff;
        text-align: center;
        border-radius: 6px;
        padding: 5px;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        margin-left: -100px;
        opacity: 0;
        transition: opacity 0.3s;
    }
    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }
</style>
""", unsafe_allow_html=True)

async def process_chunk(session, chunk, chunk_index, total_chunks):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "inputs": {"context": chunk},
        "query": f"프롬프트에 따라 제공된 context를 빠짐없이 markdown 서식으로 변환하여 코드블럭으로 출력한다. 제공된 텍스트와 동일한 언어를 사용한다. 천천히 단계 별로 작업한다. 참고 : 이 청크는 전체 {total_chunks} 중 {chunk_index + 1}번째입니다.",
        "response_mode": "streaming",
        "conversation_id": "",
        "user": "pdf_converter"
    }
    try:
        async with session.post(API_URL, json=data, headers=headers) as response:
            if response.status == 200:
                result = ""
                async for line in response.content:
                    if line:
                        decoded_line = line.decode('utf-8').strip()
                        if decoded_line.startswith("data: "):
                            try:
                                event_data = json.loads(decoded_line[6:])
                                if event_data.get("event") == "agent_thought":
                                    thought = event_data.get("thought", "")
                                    if thought.startswith("```md") and thought.endswith("```"):
                                        result += thought[5:-3].strip() + "\n\n"
                                elif event_data.get("event") == "message_end":
                                    break
                            except json.JSONDecodeError:
                                st.warning(f"JSON 파싱 오류 (청크 {chunk_index + 1}/{total_chunks})")
                return result.strip()
            else:
                st.error(f"API 오류 (청크 {chunk_index + 1}/{total_chunks}): {response.status}")
                return ""
    except Exception as e:
        st.error(f"API 요청 중 오류 발생 (청크 {chunk_index + 1}/{total_chunks}): {str(e)}")
        return ""

async def process_text(text, progress_callback):
    chunk_size = 6000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    total_chunks = len(chunks)
    results = []
    
    async with aiohttp.ClientSession() as session:
        for i, chunk in enumerate(chunks):
            progress_callback((i + 1) / total_chunks, f"청크 {i + 1}/{total_chunks} 처리 중...", "processing")
            result = await process_chunk(session, chunk, i, total_chunks)
            if result:
                results.append(result)
            progress_callback((i + 1) / total_chunks, f"청크 {i + 1}/{total_chunks} 처리 완료", "completed")
    
    return "\n\n".join(results), total_chunks

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def main():
    st.title("📄 PDF to Markdown Converter")
    
    uploaded_file = st.file_uploader("PDF 파일을 선택하세요", type="pdf")
    
    if uploaded_file is not None:
        st.success("✅ 파일이 성공적으로 업로드되었습니다!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 PDF 내용 미리보기"):
                with st.spinner("PDF 내용을 추출 중..."):
                    text = extract_text_from_pdf(BytesIO(uploaded_file.read()))
                    st.text_area("PDF 내용 미리보기:", value=text, height=400)
        
        with col2:
            if st.button("🔄 Markdown으로 변환"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                chunk_status = st.empty()
                
                with st.spinner("PDF에서 텍스트를 추출 중..."):
                    text = extract_text_from_pdf(BytesIO(uploaded_file.read()))
                progress_bar.progress(25)
                
                status_text.text("API로 텍스트를 처리 중...")
                
                async def update_progress(progress, message, status):
                    progress_bar.progress(25 + int(progress * 75))
                    status_text.text(message)
                    if status == "processing":
                        chunk_status.warning(message)
                    elif status == "completed":
                        chunk_status.success(message)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result, total_chunks = loop.run_until_complete(process_text(text, update_progress))
                
                if result:
                    progress_bar.progress(100)
                    st.success(f"✨ 변환 완료! 총 {total_chunks}개의 청크가 처리되었습니다.")
                    
                    st.download_button(
                        label="📥 Markdown 파일 다운로드",
                        data=result,
                        file_name="converted_markdown.md",
                        mime="text/markdown"
                    )
                    
                    st.markdown("<div class='output-area'>", unsafe_allow_html=True)
                    st.markdown(result)
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.error("❌ 변환된 결과가 없습니다. 자세한 에러 로그를 확인해주세요.")
    
    st.sidebar.title("📌 사용 가이드")
    st.sidebar.markdown("""
    1. PDF 파일을 업로드합니다.
    2. '📊 PDF 내용 미리보기' 버튼으로 내용을 확인합니다.
    3. '🔄 Markdown으로 변환' 버튼을 클릭하여 변환을 시작합니다.
    4. 변환된 결과를 확인하고 다운로드합니다.
    """)
    
    st.sidebar.markdown("""
    <div style="text-align: center; margin-top: 20px;">
        Made by Kyle 
        <span class="tooltip">❓
            <span class="tooltiptext">문의: cjk1306@gspoge.com</span>
        </span>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()