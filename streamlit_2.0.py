import asyncio
import aiohttp
import json
from pathlib import Path
from pypdf import PdfReader

async def async_query_api(query, filename="未知文件"):
    """异步查询API的通用函数"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    
    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一个将文本转换为Mermaid图表代码的助手"},
            {"role": "user", "content": query}
        ],
        "temperature": 0.3,
        "max_tokens": 4000
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, headers=headers, json=data, timeout=120) as response:
                response.raise_for_status()
                result = await response.json()
                return result
        except Exception as e:
            st.error(f"错误 [{filename}]: API请求失败: {str(e)}")
            return None

async def get_mermaid_code_from_text(text, filename="未知文件", diagram_type="flowchart", translate_abstract=False):
    """使用API异步获取Mermaid代码"""
    if not API_KEY:
        st.error("请先输入API密钥")
        return {"success": False, "error": "缺少API密钥"}

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

    result = await async_query_api(prompt, filename)
    if not result:
        return {
            "mermaid_code": None,
            "abstract": None,
            "success": False,
            "error": "API请求失败"
        }

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

async def async_process_files(files, diagram_type, translate_abstract, output_dir):
    """异步处理所有文件"""
    tasks = [process_file(f, diagram_type, translate_abstract, output_dir) for f in files]
    return await asyncio.gather(*tasks)

# 在Streamlit按钮点击事件中调用
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
        results = asyncio.run(async_process_files(uploaded_files, diagram_type, translate_abstract, output_dir))
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
