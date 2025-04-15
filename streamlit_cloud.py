import streamlit as st
import requests
import json
from pypdf import PdfReader
from pathlib import Path
from streamlit.components.v1 import html

# 设置页面标题和布局
st.set_page_config(
    page_title="文献转流程图工具 (Streamlit Cloud版)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 在侧边栏中添加API密钥输入
with st.sidebar:
    st.title("设置")
    DEEPSEEK_API_KEY = st.text_input("DeepSeek API Key", type="password", help="请在此处输入您的DeepSeek API密钥")
    OPENAI_API_URL = "https://api.deepseek.com/v1/chat/completions"

    translate_abstract_option = st.checkbox("生成中文摘要", value=False, help="如果勾选，将尝试从文本中提取并翻译摘要（可能增加处理时间）")

    st.markdown("---")
    st.markdown("### 使用说明")
    st.markdown("""
    1. 在左侧输入您的DeepSeek API密钥
    2. 点击 "浏览文件" 或拖拽上传一个或多个包含流程描述的文本或PDF文件 (.txt, .pdf)
    3. （可选）勾选"生成中文摘要"
    4. 点击 "批量生成流程图" 按钮
    5. 处理完成后，结果将直接显示在页面上
    """)

def get_mermaid_code_from_text(text, filename="未知文件", translate_abstract=False):
    """
    使用 DeepSeek API 将文本转换为 Mermaid 流程图代码。

    Args:
        text (str): 输入的文献段落或流程描述文本。
        filename (str): 正在处理的文件名，用于错误日志。
        translate_abstract (bool): 是否生成中文摘要

    Returns:
        dict: 包含 'mermaid_code' 和可选 'abstract' 的字典
    """
    if not DEEPSEEK_API_KEY:
        st.error("错误：请先输入DeepSeek API密钥")
        return {"mermaid_code": None, "abstract": None}

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    # 构建基础 Prompt
    base_prompt = f"""
请分析以下文本内容：
\"\"\"
{text}
\"\"\"

任务：
1. 将描述的流程转换为 Mermaid 语法的流程图代码 (graph TD)。
   - 只需要 Mermaid 代码块，不要包含任何额外的解释或文字。
   - 确保代码块以 '```mermaid' 开始，以 '```' 结束。
   - 不要在节点名称或链接中使用特殊字符（例如括号、引号），尽量使用字母数字和下划线。
"""

    # 如果需要翻译摘要，添加任务和格式说明
    if translate_abstract:
        prompt = base_prompt + f"""
2. 生成该文本内容的中文摘要。

输出格式要求：
首先输出 Mermaid 代码块，然后紧接着输出分隔符 '---摘要---'，最后输出中文摘要。
示例：
```mermaid
graph TD
    A --> B
```
---摘要---
这是中文摘要内容。

请严格按照此格式输出：
"""
    else:
        prompt = base_prompt + """
输出格式要求：
只需要输出 Mermaid 代码块。

Mermaid 代码：
"""

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个将文本转换为 Mermaid 流程图代码的助手。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4000
    }

    try:
        with st.spinner(f"[{filename}] 正在调用DeepSeek API生成Mermaid代码..."):
            response = requests.post(OPENAI_API_URL, headers=headers, json=data, timeout=120)
            response.raise_for_status()

        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            message_content = result["choices"][0]["message"]["content"].strip()

            mermaid_code = None
            abstract = None
            separator = "---摘要---"

            # 提取 Mermaid 代码块
            start_tag = "```mermaid"
            end_tag = "```"
            start_index = message_content.find(start_tag)
            end_index = message_content.find(end_tag, start_index + len(start_tag))

            if start_index != -1 and end_index != -1:
                mermaid_code = message_content[start_index + len(start_tag):end_index].strip()
                
                # 如果需要提取摘要，查找分隔符之后的内容
                if translate_abstract:
                    separator_index = message_content.find(separator, end_index)
                    if separator_index != -1:
                        abstract = message_content[separator_index + len(separator):].strip()

            # 返回结果
            if mermaid_code:
                return {"mermaid_code": mermaid_code, "abstract": abstract}
            else:
                st.error(f"错误 [{filename}]: 未能提取有效的 Mermaid 代码。")
                return {"mermaid_code": None, "abstract": None}
        else:
            st.error(f"错误 [{filename}]: API 响应格式不符合预期。")
            return {"mermaid_code": None, "abstract": None}

    except Exception as e:
        st.error(f"错误 [{filename}]: 处理 API 响应时发生错误: {e}")
        return {"mermaid_code": None, "abstract": None}

def mermaid(code: str, font_size: int = 18) -> None:
    """使用HTML组件渲染Mermaid图表"""
    html(
        f"""
        <pre class="mermaid">
            {code}
        </pre>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true, theme: "default", themeVariables: {{ fontSize: "{font_size}px" }} }});
        </script>
        """,
        height=600,  # 固定高度
    )

# 主应用界面
st.title("📊 文献转流程图工具 (Streamlit Cloud版)")
st.markdown("上传一个或多个文本文件 (.txt) 或 PDF 文件 (.pdf)，生成Mermaid流程图。")

# 文件上传区域
uploaded_files = st.file_uploader(
    "选择一个或多个文件",
    type=["txt", "pdf"],
    accept_multiple_files=True,
    help="将包含流程描述的文件拖拽到此处或点击浏览"
)

# 批量生成按钮
if st.button("批量生成流程图", type="primary", disabled=not uploaded_files):
    if uploaded_files:
        progress_bar = st.progress(0)
        status_text = st.empty()
        total_files = len(uploaded_files)
        processed_files = 0

        for uploaded_file in uploaded_files:
            processed_files += 1
            status_text.text(f"正在处理文件: {uploaded_file.name} ({processed_files}/{total_files})")

            # 读取文件内容
            literature_text = ""
            try:
                file_extension = Path(uploaded_file.name).suffix.lower()

                if file_extension == ".txt":
                    content_bytes = uploaded_file.getvalue()
                    try:
                        literature_text = content_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            literature_text = content_bytes.decode("gbk")
                        except UnicodeDecodeError:
                            st.error(f"错误 [{uploaded_file.name}]: 无法解码 TXT 文件。")
                            continue

                elif file_extension == ".pdf":
                    try:
                        pdf_reader = PdfReader(uploaded_file)
                        text_parts = [page.extract_text() for page in pdf_reader.pages if page.extract_text()]
                        literature_text = "\n".join(text_parts)
                    except Exception as pdf_e:
                        st.error(f"错误 [{uploaded_file.name}]: 读取 PDF 文件失败: {pdf_e}")
                        continue

                if not literature_text.strip():
                    st.warning(f"警告 [{uploaded_file.name}]: 文件内容为空，已跳过。")
                    continue

                # 生成 Mermaid 代码 (和可选的摘要)
                api_result = get_mermaid_code_from_text(literature_text, uploaded_file.name, translate_abstract=translate_abstract_option)
                mermaid_code = api_result["mermaid_code"]
                abstract_text = api_result["abstract"]

                if mermaid_code:
                    # 显示结果
                    with st.expander(f"结果: {uploaded_file.name}", expanded=True):
                        st.markdown(f"#### {uploaded_file.name}")
                        
                        # 显示摘要（如果存在）
                        if abstract_text:
                            st.markdown("##### 中文摘要")
                            st.markdown(abstract_text)
                        
                        # 显示流程图代码
                        st.markdown("##### Mermaid 流程图代码")
                        st.code(mermaid_code, language="mermaid")
                        
                        # 显示流程图
                        st.markdown("##### 流程图预览")
                        mermaid(mermaid_code)

            except Exception as e:
                st.error(f"错误 [{uploaded_file.name}]: 处理文件时发生意外错误: {e}")

            # 更新进度条
            progress_bar.progress(processed_files / total_files)

        status_text.text(f"处理完成！共处理 {total_files} 个文件。")
