# ```

# 这个应用具有以下特点：

# 1. **简洁的输入界面**：
#    - 提供一个大的文本框用于输入结构化面试题目
#    - 侧边栏设置API密钥和查看使用说明

# 2. **全面的输出结果**：
#    - 生成详细的参考答案，体现事业编面试的专业性
#    - 自动创建答案逻辑结构的Mermaid流程图
#    - 提取3-5个关键答题要点

# 3. **专业提示设计**：
#    - 系统提示词专门针对事业编面试设计
#    - 生成的答案符合公务员/事业编面试的规范性要求

# 4. **可视化展示**：
#    - 使用Mermaid图表清晰展示答案逻辑结构
#    - 响应式设计适应不同屏幕大小

# 5. **使用说明**：
#    - 侧边栏提供清晰的使用步骤说明
#    - 错误处理和状态提示

# 使用时，用户只需：
# 1. 在侧边栏输入DeepSeek API密钥
# 2. 在主界面输入面试题目
# 3. 点击"生成参考答案"按钮
# 4. 查看生成的参考答案、答题要点和流程图

# 这个工具特别适合准备事业编面试的考生，可以帮助他们快速理解题目要点，掌握答题结构，提高面试表现。




import streamlit as st
import requests
import json
from streamlit.components.v1 import html

# 设置页面标题和布局
st.set_page_config(
    page_title="事业编结构化面试参考答案生成器",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 在侧边栏中添加API密钥输入
with st.sidebar:
    st.title("设置")
    DEEPSEEK_API_KEY = st.text_input("DeepSeek API Key", type="password", help="请在此处输入您的DeepSeek API密钥")
    OPENAI_API_URL = "https://api.deepseek.com/v1/chat/completions"

    st.markdown("---")
    st.markdown("### 使用说明")
    st.markdown("""
    1. 在左侧输入您的DeepSeek API密钥
    2. 在下方输入框输入结构化面试题目
    3. 点击"生成参考答案"按钮
    4. 系统将生成：
       - 详细的参考答案
       - 答案结构流程图
       - 答题要点提示
    """)

def get_structured_answer(question):
    """
    使用 DeepSeek API 生成结构化面试题的参考答案和流程图
    
    Args:
        question (str): 面试题目
        
    Returns:
        dict: 包含 'answer', 'mermaid_code' 和 'key_points' 的字典
    """
    if not DEEPSEEK_API_KEY:
        st.error("错误：请先输入DeepSeek API密钥")
        return {"answer": None, "mermaid_code": None, "key_points": None}

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    # 构建Prompt
    prompt = f"""
请根据以下事业编结构化面试题目生成高质量的参考答案：

题目：{question}

要求：
1. 生成详细的参考答案，体现公务员/事业编面试的规范性和专业性
2. 将答案的逻辑结构转换为 Mermaid 语法的流程图代码 (graph TD)
   - 只需要 Mermaid 代码块，不要包含任何额外的解释或文字
   - 确保代码块以 '```mermaid' 开始，以 '```' 结束
3. 提取3-5个关键答题要点

输出格式要求：
```mermaid
graph TD
    A[开始] --> B[第一要点]
    B --> C[第二要点]
```
---关键要点---
1. 要点一
2. 要点二
3. 要点三
---参考答案---
这里是详细的参考答案内容...
"""

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一位资深的事业编面试考官，擅长生成结构化面试的参考答案和分析。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4000
    }

    try:
        with st.spinner("正在生成参考答案和流程图..."):
            response = requests.post(OPENAI_API_URL, headers=headers, json=data, timeout=120)
            response.raise_for_status()

        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            message_content = result["choices"][0]["message"]["content"].strip()

            # 初始化结果变量
            mermaid_code = None
            key_points = None
            answer = None

            # 提取 Mermaid 代码
            start_tag = "```mermaid"
            end_tag = "```"
            start_index = message_content.find(start_tag)
            end_index = message_content.find(end_tag, start_index + len(start_tag))

            if start_index != -1 and end_index != -1:
                mermaid_code = message_content[start_index + len(start_tag):end_index].strip()

            # 提取关键要点
            points_separator = "---关键要点---"
            answer_separator = "---参考答案---"
            
            points_start = message_content.find(points_separator)
            answer_start = message_content.find(answer_separator)
            
            if points_start != -1 and answer_start != -1:
                key_points = message_content[points_start + len(points_separator):answer_start].strip()
                answer = message_content[answer_start + len(answer_separator):].strip()

            return {
                "answer": answer,
                "mermaid_code": mermaid_code,
                "key_points": key_points
            }
        else:
            st.error("错误: API 响应格式不符合预期。")
            return {"answer": None, "mermaid_code": None, "key_points": None}

    except Exception as e:
        st.error(f"错误: 处理 API 响应时发生错误: {e}")
        return {"answer": None, "mermaid_code": None, "key_points": None}

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
        height=400,  # 固定高度
    )

# 主应用界面
st.title("💼 事业编结构化面试参考答案生成器")
st.markdown("输入结构化面试题目，获取专业参考答案、答题要点和逻辑流程图")

# 输入区域
question = st.text_area(
    "请输入结构化面试题目",
    height=150,
    placeholder="例如：你单位要组织一次重要的业务培训，领导交给你负责，你会如何组织？"
)

# 生成按钮
if st.button("生成参考答案", type="primary", disabled=not question):
    if question:
        result = get_structured_answer(question)
        
        if result["answer"]:
            # 显示参考答案
            st.markdown("### 参考答案")
            st.write(result["answer"])
            
            # 显示关键要点
            if result["key_points"]:
                st.markdown("### 关键答题要点")
                st.write(result["key_points"])
            
            # 显示流程图
            if result["mermaid_code"]:
                st.markdown("### 答案结构流程图")
                st.code(result["mermaid_code"], language="mermaid")
                mermaid(result["mermaid_code"])
    else:
        st.warning("请输入面试题目")
