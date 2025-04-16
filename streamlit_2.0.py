import streamlit as st
import requests
import json
import os
import zipfile
import io
import asyncio
from pathlib import Path
from pypdf import PdfReader

# 设置页面标题和布局
st.set_page_config(
    page_title="文献转图表工具 (多API版)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 支持的图表类型
DIAGRAM_TYPES = {
    "flowchart": "流程图 (graph TD/LR)",
    "sequence": "序列图 (sequenceDiagram)",
    "gantt": "甘特图 (gantt)",
    "class": "类图 (classDiagram)",
    "state": "状态图 (stateDiagram-v2)",
    "pie": "饼图 (pie)",
    "er": "实体关系图 (erDiagram)",
    "journey": "用户旅程图 (journey)",
    "mindmap": "思维导图 (mindmap)"
}

# 支持的云服务商
CLOUD_PROVIDERS = {
    "deepseek": "DeepSeek (官方)",
    "siliconflow": "硅基流动"
}

# 在侧边栏中添加设置
with st.sidebar:
    st.title("设置")
    
    # 云服务商选择
    cloud_provider = st.selectbox(
        "选择云服务商",
        options=list(CLOUD_PROVIDERS.keys()),
        format_func=lambda x: CLOUD_PROVIDERS[x]
    )
    
    # API密钥输入
    API_KEY = st.text_input(f"{CLOUD_PROVIDERS[cloud_provider]} API Key", type="password")
    
    # 根据选择的云服务商设置API URL
    if cloud_provider == "deepseek":
        API_URL = "https://api.deepseek.com/v1/chat/completions"
        MODEL_NAME = "deepseek-chat"
    elif cloud_provider == "siliconflow":
        API_URL = "https://api.siliconflow.cn/v1/chat/completions"
        MODEL_NAME = "deepseek-v3"
    
    # 图表类型选择
    diagram_type = st.selectbox(
        "选择图表类型",
        options=list(DIAGRAM_TYPES.keys()),
        format_func=lambda x: DIAGRAM_TYPES[x]
    )
    
    translate_abstract = st.checkbox("生成中文摘要", value=False)
    
    st.markdown("---")
    st.markdown("### 使用说明")
    st.markdown("""
    1. 选择API服务商并输入API密钥
    2. 选择图表类型
    3. 上传文本或PDF文件
    4. (可选)勾选生成中文摘要
    5. 点击"批量生成图表"按钮
    6. 下载处理结果
    """)

async def get_mermaid_code_from_text(text, filename="未知文件", diagram_type="flowchart", translate_abstract=False):
    """使用API异步获取Mermaid代码"""
    if not API_KEY:
        st.error("请先输入API密钥")
        return {"success": False, "error": "缺少API密钥"}

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    diagram_desc = DIAGRAM_TYPES.get(diagram_type, "流程图")
    
    prompt = f"""
请分析以下文本内容：
\"\"\"
{text}
\"\"\"

任务：
1. 将描述转换为Mermaid语法的{diagram_desc}代码
   - 只需要Mermaid代码块，不要包含任何额外的解释或文字
   - 确保代码块以'```mermaid'开始，以'```'结束
   - 严格遵守Mermaid语法规范
"""

    if translate_abstract:
        prompt += """
2. 生成该文本内容的中文摘要

输出格式要求：
首先输出Mermaid代码块，然后紧接着输出分隔符'---摘要---'，最后输出中文摘要
"""
    else:
        prompt += "输出格式要求：只需要输出Mermaid代码块"

    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": f"你是一个将文本转换为Mermaid{diagram_desc}代码的助手"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4000
    }

    try:
        async with requests.Session() as session:
            response = await session.post(API_URL, headers=headers, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()

        content = result["choices"][0]["message"]["content"]
        mermaid_code = None
        abstract = None

        # 提取Mermaid代码
        start_idx = content.find("```mermaid")
        end_idx = content.find("```", start_idx + 10) if start_idx != -1 else -1
        
        if start_idx != -1 and end_idx != -1:
            mermaid_code = content[start_idx+10:end_idx].strip()
        
        # 提取摘要
        if translate_abstract:
            sep_idx = content.find("---摘要---")
            if sep_idx != -1:
                abstract = content[sep_idx+6:].strip()

        return {
            "mermaid_code": mermaid_code,
            "abstract": abstract,
            "success": mermaid_code is not None
        }

    except Exception as e:
        return {
            "mermaid_code": None,
            "abstract": None,
            "success": False,
            "error": str(e)
        }

async def process_file(uploaded_file, diagram_type, translate_abstract, output_dir):
    """异步处理单个文件"""
    filename = uploaded_file.name
    filename_stem = Path(filename).stem
    
    try:
        # 读取文件内容
        if filename.lower().endswith('.txt'):
            content = uploaded_file.getvalue().decode('utf-8')
        elif filename.lower().endswith('.pdf'):
            pdf_reader = PdfReader(uploaded_file)
            content = "\n".join([p.extract_text() for p in pdf_reader.pages if p.extract_text()])
        else:
            return {
                "filename": filename,
                "success": False,
                "error": "不支持的文件类型"
            }

        if not content.strip():
            return {
                "filename": filename,
                "success": False,
                "error": "文件内容为空"
            }

        # 获取Mermaid代码
        result = await get_mermaid_code_from_text(
            content, filename, diagram_type, translate_abstract
        )
        
        if not result["success"]:
            return {
                "filename": filename,
                "success": False,
                "error": result.get("error", "生成Mermaid代码失败")
            }

        # 保存结果
        output_files = {}
        mmd_path = output_dir / f"{filename_stem}.mmd"
        with open(mmd_path, "w", encoding="utf-8") as f:
            f.write(result["mermaid_code"])
        output_files["mmd"] = str(mmd_path)

        if translate_abstract and result["abstract"]:
            summary_path = output_dir / f"{filename_stem}.summary.txt"
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(result["abstract"])
            output_files["summary"] = str(summary_path)

        return {
            "filename": filename,
            "success": True,
            "files": output_files,
            "mermaid_code": result["mermaid_code"],
            "abstract": result["abstract"],
            "diagram_type": diagram_type
        }

    except Exception as e:
        return {
            "filename": filename,
            "success": False,
            "error": str(e)
        }

# 主界面
st.title("📊 文献转图表工具 (多API版)")
st.markdown("上传一个或多个包含描述的文本文件 (.txt, .pdf)，批量生成Mermaid图表")

# 文件上传
uploaded_files = st.file_uploader(
    "选择文件",
    type=["txt", "pdf"],
    accept_multiple_files=True
)

# 处理状态
if "results" not in st.session_state:
    st.session_state.results = []
if "zip_buffer" not in st.session_state:
    st.session_state.zip_buffer = None

# 批量处理按钮
if st.button("批量生成图表", disabled=not uploaded_files):
    if not uploaded_files:
        st.warning("请先上传文件")
    else:
        st.session_state.results = []
        st.session_state.zip_buffer = None
        
        output_dir = Path("output_diagrams")
        output_dir.mkdir(exist_ok=True, parents=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 异步处理所有文件
        async def process_all_files():
            tasks = [process_file(f, diagram_type, translate_abstract, output_dir) 
                    for f in uploaded_files]
            return await asyncio.gather(*tasks)
        
        results = asyncio.run(process_all_files())
        st.session_state.results = results
        
        # 创建ZIP文件
        successful = [r for r in results if r["success"]]
        if successful:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zipf:
                for result in successful:
                    for file_type, path in result["files"].items():
                        try:
                            zipf.write(path, arcname=Path(path).name)
                        except Exception as e:
                            st.error(f"打包文件 {path} 失败: {e}")
            
            zip_buffer.seek(0)
            st.session_state.zip_buffer = zip_buffer
            st.success("处理完成！")
        else:
            st.warning("没有成功处理的文件")

# 显示结果
if st.session_state.results:
    st.markdown("---")
    st.subheader("处理结果")
    
    success = sum(1 for r in st.session_state.results if r["success"])
    failed = len(st.session_state.results) - success
    
    st.write(f"总文件数: {len(st.session_state.results)}")
    st.write(f"成功: {success}")
    st.write(f"失败: {failed}")
    
    if failed > 0:
        with st.expander("失败详情"):
            for r in st.session_state.results:
                if not r["success"]:
                    st.error(f"{r['filename']}: {r.get('error', '未知错误')}")
    
    # 显示成功文件的内容预览
    for r in st.session_state.results:
        if r["success"]:
            with st.expander(f"预览: {r['filename']}"):
                st.markdown(f"**图表类型**: {DIAGRAM_TYPES[r['diagram_type']]}")
                st.code(r["mermaid_code"], language="mermaid")
                if r["abstract"]:
                    st.markdown("**摘要**")
                    st.write(r["abstract"])
    
    # 下载按钮
    if st.session_state.zip_buffer:
        st.download_button(
            "下载所有结果 (ZIP)",
            data=st.session_state.zip_buffer,
            file_name="mermaid_diagrams.zip",
            mime="application/zip"
        )
