
import streamlit as st
import requests
import json
import subprocess
import os
import time
import zipfile # 导入 zipfile 库
import io      # 导入 io 库
from pathlib import Path # 导入 Path 用于处理文件名
from pypdf import PdfReader # 导入 pypdf 用于读取 PDF

# 设置页面标题和布局
st.set_page_config(
    page_title="文献转流程图工具 (批量版)",
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
    5. 处理完成后，会出现 "下载所有结果 (ZIP)" 按钮
    6. 点击下载按钮获取包含所有 .mmd、.png 和（如果选择）.summary.txt 文件的压缩包
    """)

    st.markdown("---")
    st.markdown("### 注意事项")
    st.markdown("""
    - 确保上传的文本文件内容清晰描述了流程步骤
    - 生成的流程图可能需要调整以获得最佳效果
    - 复杂的流程可能需要更详细的描述
    - 文件名将用于生成对应的输出文件名
    """)

def get_mermaid_code_from_text(text, filename="未知文件", translate_abstract=False, previous_error=None): # 增加 translate_abstract 参数
    """
    使用 DeepSeek API 将文本转换为 Mermaid 流程图代码。

    Args:
        text (str): 输入的文献段落或流程描述文本。
        filename (str): 正在处理的文件名，用于错误日志。
        previous_error (str, optional): 之前渲染时的错误信息，用于重新生成代码

    Returns:
        dict: 包含 'mermaid_code' 和可选 'abstract' 的字典，如果失败则返回 {'mermaid_code': None, 'abstract': None}。
    """
    if not DEEPSEEK_API_KEY:
        st.error("错误：请先输入DeepSeek API密钥")
        return {"mermaid_code": None, "abstract": None}

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    # 根据是否有之前的错误信息调整 prompt
    if previous_error:
        error_prompt = f"\n\n重要提示：上次生成的代码渲染失败，错误信息：{previous_error}\n请根据此错误调整生成的 Mermaid 代码。"
    else:
        error_prompt = ""
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

{error_prompt}

请严格按照此格式输出：
"""
    else:
        prompt = base_prompt + f"""
输出格式要求：
只需要输出 Mermaid 代码块。

{error_prompt}

Mermaid 代码：
"""


    data = {
        "model": "deepseek-chat", # 使用 DeepSeek 模型
        "messages": [
            {"role": "system", "content": "你是一个将文本转换为 Mermaid 流程图代码的助手。"}, # 优化 system prompt
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3, # 稍微降低温度，追求更稳定的结构
        "max_tokens": 4000
    }

    try:
        with st.spinner(f"[{filename}] 正在调用DeepSeek API生成Mermaid代码..."):
            response = requests.post(OPENAI_API_URL, headers=headers, json=data, timeout=120) # 增加超时时间以应对可能更长的处理
            response.raise_for_status() # 检查 HTTP 请求错误

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
            end_index = message_content.find(end_tag, start_index + len(start_tag)) # 从代码块开始后查找结束符

            if start_index != -1 and end_index != -1:
                mermaid_code = message_content[start_index + len(start_tag):end_index].strip()
                # 简单验证
                if not ("graph TD" in mermaid_code or "graph LR" in mermaid_code):
                    st.warning(f"[{filename}] 提取的 Mermaid 代码块似乎不包含有效的图定义 (graph TD/LR)。")

                # 如果需要提取摘要，查找分隔符之后的内容
                if translate_abstract:
                    separator_index = message_content.find(separator, end_index)
                    if separator_index != -1:
                        abstract = message_content[separator_index + len(separator):].strip()
                        if not abstract:
                             st.warning(f"[{filename}] 找到了摘要分隔符，但摘要内容为空。")
                    else:
                        st.warning(f"[{filename}] 要求了摘要，但未在 API 响应中找到分隔符 '{separator}'。")
                        # 尝试将分隔符之后的所有内容视为摘要（如果 Mermaid 代码块之后还有内容）
                        remaining_content = message_content[end_index + len(end_tag):].strip()
                        if remaining_content:
                            abstract = remaining_content
                            st.info(f"[{filename}] 将 Mermaid 代码块之后的内容视为摘要。")

            # 如果没有找到标准代码块，但可能直接返回了代码
            elif "graph TD" in message_content or "graph LR" in message_content:
                st.warning(f"[{filename}] 未找到标准 Mermaid 代码块 '```mermaid...```'，尝试提取包含 'graph' 的部分作为代码。")
                lines = message_content.split('\n')
                mermaid_lines = []
                in_code_block = False
                for line in lines:
                    stripped_line = line.strip()
                    if stripped_line.startswith("graph TD") or stripped_line.startswith("graph LR"):
                        in_code_block = True
                    if in_code_block and stripped_line and not stripped_line.startswith("```"):
                        # 遇到摘要分隔符时停止提取代码
                        if translate_abstract and stripped_line.startswith(separator):
                            break
                        mermaid_lines.append(line)
                if mermaid_lines:
                    mermaid_code = "\n".join(mermaid_lines).strip()

                # 如果需要提取摘要，查找分隔符
                if translate_abstract:
                    separator_index = message_content.find(separator)
                    if separator_index != -1:
                        abstract = message_content[separator_index + len(separator):].strip()
                        if not abstract:
                             st.warning(f"[{filename}] 找到了摘要分隔符，但摘要内容为空。")
                    else:
                         st.warning(f"[{filename}] 要求了摘要，但未在 API 响应中找到分隔符 '{separator}'。")

            # 如果连 graph 都找不到，但 API 有返回
            elif message_content:
                 st.warning(f"[{filename}] API 返回内容中未找到有效的 Mermaid 代码。")
                 # 如果要求摘要，看看是否有分隔符
                 if translate_abstract:
                    separator_index = message_content.find(separator)
                    if separator_index != -1:
                        # 认为分隔符前是无效代码，分隔符后是摘要
                        abstract = message_content[separator_index + len(separator):].strip()
                        st.warning(f"[{filename}] 找到了摘要分隔符，但未找到有效代码。")
                    else:
                        # 无法区分代码和摘要，返回错误
                        st.error(f"错误 [{filename}]: 未能从 API 响应中提取有效的 Mermaid 代码或摘要。")
                        st.text(f"API 返回内容 ({filename}):")
                        st.code(message_content, language="text")
                        return {"mermaid_code": None, "abstract": None}

            # 返回结果
            if mermaid_code:
                return {"mermaid_code": mermaid_code, "abstract": abstract}
            else:
                # 如果只找到了摘要，也算部分成功？或者标记为失败？当前逻辑下无代码则失败
                st.error(f"错误 [{filename}]: 最终未能提取有效的 Mermaid 代码。")
                if abstract:
                    st.info(f"[{filename}] 但似乎提取到了摘要内容。")
                    st.text("摘要内容：")
                    st.text(abstract)
                return {"mermaid_code": None, "abstract": None}
        elif "error" in result: # This elif belongs inside the 'if "choices" in result...' block's scope
            st.error(f"错误 [{filename}]: API 返回错误: {result['error'].get('message', '未知错误')}")
            st.json(result)
            return {"mermaid_code": None, "abstract": None}
        else: # This else also belongs inside the 'if "choices" in result...' block's scope
            st.error(f"错误 [{filename}]: API 响应格式不符合预期。")
            st.json(result)
            return {"mermaid_code": None, "abstract": None}

    except requests.exceptions.Timeout:
        st.error(f"错误 [{filename}]: 调用 API 超时。")
        return {"mermaid_code": None, "abstract": None}
    except requests.exceptions.RequestException as e:
        st.error(f"错误 [{filename}]: 调用 API 时发生网络错误: {e}")
        return {"mermaid_code": None, "abstract": None}
    except json.JSONDecodeError:
        st.error(f"错误 [{filename}]: 解析 API 响应失败。响应内容: {response.text}")
        return {"mermaid_code": None, "abstract": None}
    except Exception as e:
        st.error(f"错误 [{filename}]: 处理 API 响应时发生未知错误: {e}")
        return {"mermaid_code": None, "abstract": None}


def render_mermaid_to_image(mermaid_code: str, output_path: str, filename="未知文件", original_text=None, translate_abstract=False, max_retries=2): # 添加 translate_abstract
    """
    使用 mermaid-cli 将 Mermaid 代码渲染为图片

    Args:
        mermaid_code (str): Mermaid 代码
        output_path (str): 输出图片路径 (现在是完整路径)
        filename (str): 正在处理的文件名，用于日志。
        original_text (str): 原始文本，用于重新生成代码
        max_retries (int): 最大重试次数
    """
    retry_count = 0
    current_mermaid_code = mermaid_code # 保存当前要渲染的代码

    # 确保输出目录存在
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    while retry_count < max_retries:
        # 临时文件使用唯一名称，避免冲突
        temp_file_path = output_dir / f"temp_{Path(output_path).stem}_{retry_count}.mmd"

        try:
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(current_mermaid_code)

            # 使用 mmdc.cmd 的绝对路径（从环境变量或固定路径获取）
            # 尝试从环境变量获取，否则使用硬编码路径
            mmdc_path = os.environ.get("MMDC_PATH", r"C:\Users\caixukun\AppData\Roaming\npm\mmdc.cmd")
            if not Path(mmdc_path).is_file():
                 st.error(f"错误 [{filename}]: 找不到 mermaid-cli (mmdc) 执行文件: {mmdc_path}。请确保已安装并配置路径。")
                 # 尝试清理临时文件
                 if temp_file_path.exists():
                     os.remove(temp_file_path)
                 return False


            # 运行 mermaid-cli
            with st.spinner(f"[{filename}] 正在渲染流程图 (尝试 {retry_count + 1}/{max_retries})..."):
                process = subprocess.run([
                    mmdc_path,
                    "-i", str(temp_file_path),
                    "-o", output_path,
                    "-t", "default",
                    "--backgroundColor", "white",
                    "--width", "2000",   # 增加宽度
                    "--height", "1500",  # 增加高度
                    "--scale", "3"       # 调整缩放
                ], check=False, capture_output=True, text=True, encoding='utf-8') # check=False 手动检查

            # 删除临时文件
            if temp_file_path.exists():
                os.remove(temp_file_path)

            # 检查渲染是否成功
            if process.returncode == 0 and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                # st.success(f"成功生成流程图图片: {Path(output_path).name}") # 不在函数内显示成功消息
                return True
            else:
                # 记录详细错误
                error_message = f"mermaid-cli 渲染失败 (返回码: {process.returncode})"
                if process.stderr:
                    error_message += f"\n错误输出:\n{process.stderr}"
                if process.stdout: # 有时错误信息在 stdout
                    error_message += f"\n标准输出:\n{process.stdout}"
                if not Path(output_path).exists():
                     error_message += "\n输出文件未生成。"
                elif Path(output_path).stat().st_size == 0:
                     error_message += "\n输出文件大小为 0。"

                st.warning(f"警告 [{filename}]: {error_message}")

                # 如果有原始文本且未达到最大重试次数，尝试重新生成代码
                if original_text and retry_count < max_retries - 1:
                    retry_count += 1
                    st.warning(f"[{filename}] 尝试重新生成 Mermaid 代码 (尝试 {retry_count}/{max_retries})...")

                    # 获取错误信息用于 prompt
                    render_error_msg = f"mermaid-cli 错误: {process.stderr}" if process.stderr else error_message

                    # 重新生成代码
                    # 重新生成代码，需要传递 translate_abstract 状态
                    regen_result = get_mermaid_code_from_text(original_text, filename, translate_abstract, render_error_msg)
                    new_mermaid_code = regen_result["mermaid_code"]
                    # 注意：这里没有处理重新生成的摘要，因为主要目标是修复渲染错误

                    if not new_mermaid_code:
                        st.error(f"[{filename}] 重新生成 Mermaid 代码失败。")
                        return False # 无法重新生成，渲染失败

                    st.info(f"[{filename}] 重新生成的 Mermaid 代码:")
                    st.code(new_mermaid_code, language="mermaid")
                    current_mermaid_code = new_mermaid_code # 更新要渲染的代码
                    # 继续循环尝试渲染新代码
                    continue
                else:
                    # 达到重试次数或没有原始文本
                    st.error(f"[{filename}] 渲染失败，已达到最大重试次数或无法重新生成代码。")
                    return False

        except FileNotFoundError:
             st.error(f"错误 [{filename}]: 找不到 mermaid-cli (mmdc) 执行文件: {mmdc_path}。请确保已安装并配置路径。")
             # 尝试清理临时文件
             if temp_file_path.exists():
                 os.remove(temp_file_path)
             return False
        except Exception as e:
            st.error(f"错误 [{filename}]: 处理 Mermaid 图表时发生未知错误: {e}")
             # 尝试清理临时文件
            if temp_file_path.exists():
                os.remove(temp_file_path)
            return False

    # 如果循环结束仍未成功
    st.error(f"[{filename}] 经过 {max_retries} 次尝试仍未能生成有效的流程图图片。")
    return False


# 主应用界面
st.title("📊 文献转流程图工具 (批量版)")
st.markdown("上传一个或多个包含流程描述的文本文件 (.txt)，批量生成Mermaid流程图和图片。")

# 文件上传区域
uploaded_files = st.file_uploader(
    "选择一个或多个文本文件 (.txt)",
    type=["txt", "pdf"], # 允许上传 txt 和 pdf 文件
    accept_multiple_files=True,
    help="将包含流程描述的文本文件拖拽到此处或点击浏览"
)

# 用于存储处理结果的 session state
if 'results' not in st.session_state:
    st.session_state.results = []
if 'zip_buffer' not in st.session_state:
    st.session_state.zip_buffer = None
if 'display_results' not in st.session_state:
    st.session_state.display_results = {}

# 批量生成按钮
if st.button("批量生成流程图", type="primary", disabled=not uploaded_files):
    if uploaded_files:
        st.session_state.results = [] # 清空旧结果
        st.session_state.zip_buffer = None # 清空旧的 zip 缓存
        st.session_state.display_results = {} # 清空显示结果
        output_dir = Path("output_flowcharts") # 定义输出目录
        output_dir.mkdir(parents=True, exist_ok=True) # 创建输出目录

        progress_bar = st.progress(0)
        status_text = st.empty()
        total_files = len(uploaded_files)
        processed_files = 0
        all_results = [] # 存储所有文件的结果路径

        for uploaded_file in uploaded_files:
            processed_files += 1
            filename_stem = Path(uploaded_file.name).stem # 获取不带扩展名的文件名
            status_text.text(f"正在处理文件: {uploaded_file.name} ({processed_files}/{total_files})")

            # 读取文件内容
            literature_text = ""
            try:
                file_extension = Path(uploaded_file.name).suffix.lower()

                if file_extension == ".txt":
                    # 处理 TXT 文件
                    content_bytes = uploaded_file.getvalue()
                    try:
                        literature_text = content_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            literature_text = content_bytes.decode("gbk")
                            st.info(f"[{uploaded_file.name}] TXT 文件以 GBK 编码读取。")
                        except UnicodeDecodeError:
                             st.error(f"错误 [{uploaded_file.name}]: 无法使用 UTF-8 或 GBK 解码 TXT 文件。请确保文件编码正确。")
                             all_results.append({"filename": uploaded_file.name, "success": False, "error": "TXT 文件编码错误"})
                             progress_bar.progress(processed_files / total_files)
                             continue # 处理下一个文件

                elif file_extension == ".pdf":
                    # 处理 PDF 文件
                    try:
                        pdf_reader = PdfReader(uploaded_file)
                        text_parts = [page.extract_text() for page in pdf_reader.pages if page.extract_text()]
                        literature_text = "\n".join(text_parts)
                        if not literature_text.strip():
                             st.warning(f"警告 [{uploaded_file.name}]: 从 PDF 文件提取的文本为空。")
                             # 即使为空也继续处理，让后续步骤判断
                        else:
                             st.info(f"[{uploaded_file.name}] PDF 文件内容已提取。")
                    except Exception as pdf_e:
                        st.error(f"错误 [{uploaded_file.name}]: 读取 PDF 文件失败: {pdf_e}")
                        all_results.append({"filename": uploaded_file.name, "success": False, "error": f"读取 PDF 失败: {pdf_e}"})
                        progress_bar.progress(processed_files / total_files)
                        continue # 处理下一个文件
                else:
                    # 不应发生，因为 file_uploader 限制了类型，但作为保险
                    st.error(f"错误 [{uploaded_file.name}]: 不支持的文件类型 '{file_extension}'。")
                    all_results.append({"filename": uploaded_file.name, "success": False, "error": "不支持的文件类型"})
                    progress_bar.progress(processed_files / total_files)
                    continue # 处理下一个文件

            except Exception as e:
                st.error(f"错误 [{uploaded_file.name}]: 读取或处理文件时发生意外错误: {e}")
                all_results.append({"filename": uploaded_file.name, "success": False, "error": f"文件处理失败: {e}"})
                progress_bar.progress(processed_files / total_files)
                continue # 处理下一个文件

            if not literature_text.strip():
                st.warning(f"警告 [{uploaded_file.name}]: 文件内容为空，已跳过。")
                all_results.append({"filename": uploaded_file.name, "success": False, "error": "文件为空"})
                progress_bar.progress(processed_files / total_files)
                continue

            # 1. 生成 Mermaid 代码 (和可选的摘要)
            api_result = get_mermaid_code_from_text(literature_text, uploaded_file.name, translate_abstract=translate_abstract_option)
            mermaid_code = api_result["mermaid_code"]
            abstract_text = api_result["abstract"]

            if mermaid_code:
                # 保存 Mermaid 代码文件
                output_mmd_file = output_dir / f"{filename_stem}.mmd"
                mmd_success = False
                try:
                    with open(output_mmd_file, "w", encoding="utf-8") as f:
                        f.write(mermaid_code)
                    st.info(f"[{uploaded_file.name}] Mermaid 代码已保存。")
                    mmd_success = True
                except IOError as e:
                    st.error(f"错误 [{uploaded_file.name}]: 无法写入 Mermaid 文件 '{output_mmd_file.name}': {e}")

                # 保存摘要文件（如果存在）
                output_summary_file = None
                summary_success = False # Default to False
                if translate_abstract_option: # Only evaluate summary success if it was requested
                    if abstract_text:
                        output_summary_file = output_dir / f"{filename_stem}.summary.txt"
                        try:
                            with open(output_summary_file, "w", encoding="utf-8") as f:
                                f.write(abstract_text)
                            st.info(f"[{uploaded_file.name}] 中文摘要已保存。")
                            summary_success = True
                        except IOError as e:
                            st.error(f"错误 [{uploaded_file.name}]: 无法写入摘要文件 '{output_summary_file.name}': {e}")
                            summary_success = False # Explicitly mark as failed if write error
                    else:
                         st.warning(f"[{uploaded_file.name}] 要求了摘要但未能生成或提取。")
                         summary_success = False # Mark as failed if requested but not generated/extracted
                else:
                     summary_success = True # If abstract was not requested, it doesn't affect success

                # 2. 渲染为图片
                output_image_file = output_dir / f"{filename_stem}.png"
                render_success = render_mermaid_to_image(mermaid_code, str(output_image_file), uploaded_file.name, literature_text, translate_abstract_option)

                if render_success:
                     st.info(f"[{uploaded_file.name}] 流程图图片已生成。")
                else:
                     st.error(f"[{uploaded_file.name}] 未能生成流程图图片。")

                # 记录结果
                result = {
                    "filename": uploaded_file.name,
                    # 整体成功需要代码、图片、（如果要求了）摘要都成功
                    "success": mmd_success and render_success and summary_success,
                    "mmd_path": str(output_mmd_file) if mmd_success else None,
                    "png_path": str(output_image_file) if render_success else None,
                    "summary_path": str(output_summary_file) if summary_success and output_summary_file else None,
                    "error": None if (mmd_success and render_success and summary_success) else "文件处理中存在错误", # 更通用的错误消息
                    "mermaid_code": mermaid_code if mmd_success else None,
                    "abstract": abstract_text if summary_success and abstract_text else None
                }
                all_results.append(result)
                
                # 保存用于显示的结果
                if result["success"]:
                    st.session_state.display_results[uploaded_file.name] = {
                        "mermaid_code": mermaid_code,
                        "abstract": abstract_text if translate_abstract_option and abstract_text else None,
                        "image_path": str(output_image_file) if render_success else None
                    }

            else: # mermaid_code is None
                st.error(f"错误 [{uploaded_file.name}]: 未能生成 Mermaid 代码。")
                all_results.append({"filename": uploaded_file.name, "success": False, "error": "生成 Mermaid 代码失败"})

            # 更新进度条
            progress_bar.progress(processed_files / total_files)

        status_text.text(f"处理完成！共处理 {total_files} 个文件。")
        st.session_state.results = all_results # 保存结果到 session state

        # 3. 创建 ZIP 文件
        successful_files = [r for r in all_results if r["success"]]
        if successful_files:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                st.write("正在打包结果...")
                zip_progress = st.progress(0)
                files_to_zip = 0
                zipped_files = 0
                # 计算总文件数 (mmd, png, summary)
                for result in successful_files:
                    if result.get("mmd_path") and Path(result["mmd_path"]).exists():
                        files_to_zip += 1
                    if result.get("png_path") and Path(result["png_path"]).exists():
                        files_to_zip += 1
                    if result.get("summary_path") and Path(result["summary_path"]).exists():
                        files_to_zip += 1

                if files_to_zip == 0:
                    st.warning("没有找到可打包的文件。")
                    st.session_state.zip_buffer = None # 确保 zip buffer 为空
                    zip_progress.empty()
                else:
                    # 添加文件到 zip
                    for i, result in enumerate(successful_files):
                        # 添加 mmd 文件
                        if result.get("mmd_path") and Path(result["mmd_path"]).exists():
                            try:
                                zipf.write(result["mmd_path"], arcname=Path(result["mmd_path"]).name)
                                zipped_files += 1
                                if files_to_zip > 0: zip_progress.progress(zipped_files / files_to_zip)
                            except Exception as e:
                                st.error(f"打包文件 {Path(result['mmd_path']).name} 时出错: {e}")
                        # 添加 png 文件
                        if result.get("png_path") and Path(result["png_path"]).exists():
                            try:
                                zipf.write(result["png_path"], arcname=Path(result["png_path"]).name)
                                zipped_files += 1
                                if files_to_zip > 0: zip_progress.progress(zipped_files / files_to_zip)
                            except Exception as e:
                                st.error(f"打包文件 {Path(result['png_path']).name} 时出错: {e}")
                        # 添加 summary 文件
                        if result.get("summary_path") and Path(result["summary_path"]).exists():
                            try:
                                zipf.write(result["summary_path"], arcname=Path(result["summary_path"]).name)
                                zipped_files += 1
                                if files_to_zip > 0: zip_progress.progress(zipped_files / files_to_zip)
                            except Exception as e:
                                st.error(f"打包文件 {Path(result['summary_path']).name} 时出错: {e}")

                    # 在循环结束后，但在 with 块结束前 seek(0)
                    zip_buffer.seek(0)
                    st.session_state.zip_buffer = zip_buffer # 保存 zip buffer 到 session state
                    st.success("所有成功处理的文件已打包成 ZIP！")
                    zip_progress.empty() # 清除打包进度条
        else: # Corresponds to 'if successful_files:'
            st.warning("没有成功处理的文件可供打包。")

# 显示处理结果摘要
if st.session_state.results:
    st.markdown("---")
    st.subheader("处理结果摘要")
    success_count = sum(1 for r in st.session_state.results if r.get("success")) # 使用 .get() 更安全
    fail_count = len(st.session_state.results) - success_count
    st.write(f"总文件数: {len(st.session_state.results)}")
    st.write(f"成功: <span style='color:green'>{success_count}</span>", unsafe_allow_html=True)
    st.write(f"失败: <span style='color:red'>{fail_count}</span>", unsafe_allow_html=True)

    # 如果有失败的文件，显示详情
    if fail_count > 0:
        with st.expander("查看失败详情"):
            for result in st.session_state.results:
                if not result.get("success"):
                    error_msg = result.get('error', '未知错误') # 获取错误信息
                    st.error(f"**{result.get('filename', '未知文件')}**: {error_msg}")

    # 显示 ZIP 下载按钮 (如果 zip buffer 存在且非空)
    if st.session_state.zip_buffer and st.session_state.zip_buffer.getbuffer().nbytes > 0:
        st.download_button(
            label="下载所有结果 (ZIP)",
            data=st.session_state.zip_buffer,
            file_name="flowchart_results.zip",
            mime="application/zip",
            key="zip_download" # 添加 key 避免重复渲染问题
        )
    # 如果所有文件都失败了，显示警告
    elif fail_count == len(st.session_state.results) and len(st.session_state.results) > 0:
         st.warning("所有文件处理失败，无法生成 ZIP 包。")

# 显示成功处理的文件结果
if st.session_state.display_results:
    st.markdown("---")
    st.subheader("生成结果预览")
    
    # 创建选项卡式界面
    tabs = st.tabs([f"结果 {i+1}" for i in range(len(st.session_state.display_results))])
    
    for idx, (filename, result_data) in enumerate(st.session_state.display_results.items()):
        with tabs[idx]:
            st.markdown(f"#### 文件名: {filename}")
            
            # 显示摘要（如果存在）
            if result_data.get("abstract"):
                with st.expander("查看摘要"):
                    st.markdown(result_data["abstract"])
            
            # 显示流程图代码
            st.markdown("##### Mermaid 流程图代码")
            st.code(result_data["mermaid_code"], language="mermaid")
            
            # 显示流程图图片
            st.markdown("##### 流程图预览")
            if result_data.get("image_path") and Path(result_data["image_path"]).exists():
                st.image(result_data["image_path"], use_column_width=True)
            else:
                st.warning("无法加载流程图图片")
