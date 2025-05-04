import os
import json
import re
from typing import List, Dict, Any
import streamlit as st
from tavily import TavilyClient
import datetime

# 设置页面配置
st.set_page_config(
    page_title="学术论文评审系统",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# 加载本地CSS文件（如果存在）
try:
    local_css("style.css")
except:
    # 默认样式
    st.markdown("""
    <style>
    /* 主容器样式 */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* 标题样式 */
    .stMarkdown h1 {
        color: #2c3e50;
        border-bottom: 2px solid #3498db;
        padding-bottom: 0.3em;
    }
    
    /* 输入框样式 */
    .stTextInput>div>div>input {
        background-color: #ffffff;
        border-radius: 8px;
    }
    
    /* 按钮样式 */
    .stButton>button {
        background-color: #3498db;
        color: white;
        border-radius: 8px;
        padding: 0.5em 1em;
        border: none;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        background-color: #2980b9;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
    /* 标签页样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: #e8f4fc;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        transition: all 0.3s;
    }
    
    .stTabs [aria-selected="true"] {
        background: #3498db;
        color: white;
    }
    
    /* 侧边栏样式 */
    [data-testid="stSidebar"] {
        background: linear-gradient(145deg, #2c3e50, #34495e);
        color: white;
    }
    
    [data-testid="stSidebar"] .stMarkdown h2 {
        color: #ecf0f1;
        border-bottom: 1px solid #7f8c8d;
    }
    
    /* 卡片样式 */
    .stExpander {
        background: white;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 1em;
    }
    
    /* 状态消息样式 */
    [data-testid="stStatusWidget"] {
        border-radius: 10px;
    }
    
    /* 响应式调整 */
    @media (max-width: 768px) {
        .stTextInput>div>div>input {
            font-size: 14px;
        }
    }
    
    /* 引用样式 */
    blockquote {
        border-left: 4px solid #3498db;
        padding-left: 1em;
        color: #7f8c8d;
        font-style: italic;
    }
    </style>
    """, unsafe_allow_html=True)

class AcademicPaperReviewer:
    def __init__(self, tavily_api_key: str, deepseek_api_key: str, 
                 deepseek_api_base: str = "https://api.deepseek.com"):
        self.tavily_client = TavilyClient(api_key=tavily_api_key)
        self.deepseek_api_key = deepseek_api_key
        self.deepseek_api_base = deepseek_api_base
        self.deepseek_model = "deepseek-chat"
        self.professional_domains = [
            "agupubs.onlinelibrary.wiley.com",
            "journals.ametsoc.org",
            "rmets.onlinelibrary.wiley.com",
            "wmo.int",
            "nasa.gov",
            "arxiv.org",
            "springer.com",
            "nature.com",
            "researchgate.net",
            "science.org",
            "pnas.org",
            "jstor.org"
        ]
        
    def search_with_tavily(self, query: str, max_results: int = 15) -> List[Dict]:
        """
        使用Tavily官方客户端进行专业学术搜索
        """
        st.info(f"正在使用Tavily搜索学术信息: {query}")
        
        try:
            response = self.tavily_client.search(
                query=query,
                search_depth="advanced",
                include_answer=False,
                include_raw_content=False,
                max_results=max_results,
                include_domains=self.professional_domains,
                exclude_domains=["wikipedia.org"]
            )
            
            results = []
            for result in response.get("results", []):
                if any(domain in result.get("url", "") for domain in self.professional_domains):
                    results.append({
                        "title": result.get("title", ""),
                        "snippet": result.get("content", ""),
                        "url": result.get("url", ""),
                        "published_date": result.get("published_date", ""),
                        "authors": result.get("authors", []),
                        "score": result.get("score", 0)
                    })
            
            if results:
                results.sort(key=lambda x: x["score"], reverse=True)
                st.success(f"搜索完成，找到 {len(results)} 条结果。")
                return results[:max_results]
            
            st.warning("未找到符合条件的结果")
            return []
            
        except Exception as e:
            st.error(f"Tavily搜索出错: {e}")
            return []

    def process_with_multiple_experts(self, combined_text: str, topic: str) -> Dict[str, str]:
        """
        多专家协作处理文本
        """
        expert_prompts = {
            "总结专家": """请根据以下搜索结果，撰写关于主题"{topic}"的文献综述。
            文章应包含关键事实、背景信息和相关概念。
            请确保内容准确、流畅，并整合来自不同来源的信息。
            请使用中文撰写，严格遵循WMO术语标准。""",
            "问题生成专家": """请根据以下关于主题"{topic}"的搜索结果摘要，提出相关的研究问题。
            请以列表形式列出这些问题，并标注推荐分析方法。
            请使用中文回答。""",
            "关键概念专家": """请从以下文本中提取与主题"{topic}"相关的关键概念和术语。
            请确保使用WMO标准术语。
            请以列表形式列出这些概念。""",
            "未来方向专家": """请根据以下关于主题"{topic}"的搜索结果摘要，提出可能的未来研究方向。
            请以列表形式列出这些建议。
            请使用中文回答。"""
        }
        
        expert_outputs = {}
        progress_bar = st.progress(0)
        total_experts = len(expert_prompts)
        
        for i, (expert_name, prompt_template) in enumerate(expert_prompts.items()):
            progress_bar.progress((i + 1) / total_experts, text=f"{expert_name}正在处理...")
            prompt = prompt_template.format(topic=topic)
            output = self._call_deepseek(prompt, combined_text)
            expert_outputs[expert_name] = output
        
        progress_bar.empty()
        return expert_outputs

    def format_academic_output(self, expert_results: Dict[str, str], references: List[Dict]) -> str:
        """
        按照knowledge_storm风格格式化输出
        """
        first_expert_output = list(expert_results.values())[0]
        title_line = first_expert_output.splitlines()[0] if first_expert_output else "文献综述"
        formatted = f"# {title_line}\n\n"
        
        # 添加摘要部分
        if "总结专家" in expert_results:
            formatted += "## 摘要\n"
            formatted += expert_results["总结专家"] + "\n\n"
        
        # 添加背景部分
        formatted += "## 背景\n"
        formatted += self._extract_background(expert_results["总结专家"]) + "\n\n"
        
        # 添加方法论部分
        if "问题生成专家" in expert_results:
            formatted += "## 方法论\n"
            formatted += self._format_methodology(expert_results["问题生成专家"]) + "\n\n"
        
        # 添加结果和讨论
        formatted += "## 结果与讨论\n"
        formatted += self._format_discussion(expert_results) + "\n\n"
        
        # 添加参考文献
        formatted += "## 参考文献\n"
        for i, ref in enumerate(references, 1):
            formatted += f"[{i}] {self._format_citation(ref)}\n\n"
        
        return formatted

    def _extract_background(self, content: str) -> str:
        """从专家输出中提取背景信息"""
        prompt = """请从以下文本中提取背景信息部分：
        {content}
        
        请保持学术严谨性，使用WMO标准术语。"""
        return self._call_deepseek(prompt, content)

    def _format_methodology(self, content: str) -> str:
        """格式化方法论部分"""
        prompt = """请将以下分析方法建议整理为规范的方法论描述：
        {content}
        
        请按以下结构组织：
        1. 数据来源
        2. 分析方法
        3. 技术路线"""
        return self._call_deepseek(prompt, content)

    def _format_discussion(self, expert_results: Dict[str, str]) -> str:
        """整合讨论部分"""
        combined = "\n\n".join(expert_results.values())
        prompt = """请根据以下专家意见，撰写综合讨论：
        {combined}
        
        请突出：
        1. 主要发现
        2. 研究限制
        3. 未来方向"""
        return self._call_deepseek(prompt, combined)

    def _format_citation(self, ref: Dict) -> str:
        """WMO标准参考文献格式"""
        authors = ", ".join(ref.get("authors", ["匿名作者"]))
        year = ref.get("published_date", "").split("-")[0] or "n.d."
        title = ref.get("title", "无标题")
        url = ref.get("url", "")
        return f"{authors} ({year}). {title}. [Online] Available: {url} [Accessed: {datetime.date.today().strftime('%d %b %Y')}]"

    def _call_deepseek(self, prompt: str, text: str) -> str:
        """调用DeepSeek API"""
        import requests
        
        # 深度思考模式下的去AI味提示词
        deai_system_prompt = """# Role
你是一位资深的语言风格转换与文本润色专家，需要帮助用户将 AI 生成的文章改写成具有人性化和自然表达的内容。文章应避免机械感，确保在语言风格、情感表达、逻辑结构等方面与人类写作保持一致。

# Profile
作为语言风格转换专家，你精通将 AI 生成的文本调整为自然的人类写作风格，口语化表达。你对人类写作特征有深刻理解，能够识别并修改 AI 文本中的典型特征，如重复用语、情感缺失、逻辑生硬等问题。

# Skills
1. 具备文本分析能力，能识别 AI 文本中的模板化语言与人类写作的差异
2. 掌握创造性写作技巧，通过词汇替换、句式调整、情感增强等手段优化文章
3. 具有细致的编辑能力，能优化文章结构和逻辑，确保整体流畅性

# Goals
调整 AI 文章至接近人类写作风格，文章内容口语化，降低AI特征，提升自然度和个性化
增加情感表达，提高内容吸引力和可读性

# Constraints
调整时保持原有信息准确性，避免改变文章基本意图和内容，确保语言多样性和表现力。

# Workflow
1. 分析 AI 文本特征，识别重复词汇、刻板句式等问题
2. 调整词汇和句式，增加语言多样性
3. 加入情感色彩和个性化表达、口语化表达
4. 优化文章结构和逻辑连贯性
5. 校对润色，确保表达准确清晰
6. 进行总体评估，提供修改说明和效果分析

现在请处理以下内容，让其读起来不像AI生成，并且仍然要保持学术论文的特点："""
        
        url = f"{self.deepseek_api_base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}"
        }
        
        # 将去AI味提示词与原始提示结合
        full_prompt = f"{prompt}\n\n{text}"
        
        payload = {
            "model": self.deepseek_model,
            "messages": [
                {"role": "system", "content": deai_system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            "temperature": 0.7,  # 提高temperature以增加创造性
            "top_p": 0.9,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            st.error(f"DeepSeek API错误: {e}")
            return f"处理错误: {e}"

def main():

    
    # 页面标题
    st.title("📚 学术论文评审系统")
    st.markdown("""
    <div style="background-color:#3498db;padding:20px;border-radius:10px;margin-bottom:20px;">
        <h2 style="color:white;margin:0;">专业学术文献分析与评审工具</h2>
        <p style="color:white;margin:0;">基于AI的文献综述、问题分析和研究方向预测</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 侧边栏配置
    with st.sidebar:
        st.markdown("""
        <div style="background-color:#2980b9;padding:15px;border-radius:10px;margin-bottom:20px;">
            <h3 style="color:white;margin:0;">系统配置</h3>
        </div>
        """, unsafe_allow_html=True)
        
        tavily_api_key = st.text_input("Tavily API Key", type="password", value=os.getenv("TAVILY_API_KEY", ""), 
                                     help="从Tavily官网获取API密钥")
        deepseek_api_key = st.text_input("DeepSeek API Key", type="password", value=os.getenv("DEEPSEEK_API_KEY", ""),
                                       help="从DeepSeek官网获取API密钥")
        max_results = st.slider("最大搜索结果数", 5, 20, 10, 
                               help="控制每次搜索返回的文献数量")
        
        st.markdown("---")
        st.markdown("""
        <div style="background-color:#2980b9;padding:15px;border-radius:10px;">
            <h3 style="color:white;margin:0;">关于系统</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background-color:#34495e;padding:15px;border-radius:10px;color:white;">
            <p>这是一个学术论文评审系统，能够:</p>
            <ul>
                <li>从专业学术数据库搜索文献</li>
                <li>生成文献综述</li>
                <li>分析研究问题和方法</li>
                <li>提出未来研究方向</li>
            </ul>
            <p style="font-size:0.8em;text-align:right;">版本 1.0.0</p>
        </div>
        """, unsafe_allow_html=True)
    
    # 主界面
    tab1, tab2 = st.tabs(["📖 文献评审", "⚙️ 高级选项"])
    
    with tab1:
        col1, col2 = st.columns([3, 1])
        with col1:
            topic = st.text_input("请输入研究主题", placeholder="例如: 气候变化对农业的影响", 
                                help="输入您想要研究的主题或论文题目")
        with col2:
            st.markdown("<div style='height:52px;display:flex;align-items:center;'>", unsafe_allow_html=True)
            if st.button("开始评审", type="primary", use_container_width=True):
                st.session_state.run_review = True
            st.markdown("</div>", unsafe_allow_html=True)
        
        if st.session_state.get("run_review", False):
            if not tavily_api_key or not deepseek_api_key:
                st.error("请提供Tavily和DeepSeek的API密钥")
                return
                
            if not topic:
                st.error("请输入研究主题")
                return
                
            safe_topic = re.sub(r'[\\/*?:"<>|]', "", topic)
            
            # 初始化评审器
            reviewer = AcademicPaperReviewer(tavily_api_key, deepseek_api_key)
            
            # 显示处理状态
            with st.status("正在处理...", expanded=True) as status:
                # 学术搜索
                st.write("🔍 正在搜索学术文献...")
                search_results = reviewer.search_with_tavily(safe_topic, max_results)
                
                if not search_results:
                    status.update(label="处理完成 - 未找到结果", state="complete")
                    return
                
                # 多专家处理
                st.write("🧠 正在使用专家系统分析文献...")
                combined_text = "\n\n".join([
                    f"标题: {r['title']}\n作者: {', '.join(r.get('authors', []))}\n摘要: {r['snippet']}"
                    for r in search_results
                ])
                expert_results = reviewer.process_with_multiple_experts(combined_text, safe_topic)
                
                # 格式化输出
                st.write("📝 正在格式化输出...")
                formatted = reviewer.format_academic_output(expert_results, search_results)
                
                status.update(label="处理完成!", state="complete")
            
            # 显示结果
            st.subheader("📄 文献综述")
            st.markdown(formatted, unsafe_allow_html=True)
            
            # 显示原始搜索结果
            with st.expander("🔍 查看原始搜索结果", expanded=False):
                for i, result in enumerate(search_results, 1):
                    st.markdown(f"""
                    <div style="background-color:#f0f8ff;padding:15px;border-radius:10px;margin-bottom:15px;">
                        <h4 style="color:#2c3e50;margin-top:0;">[{i}] {result['title']}</h4>
                        <p><b>作者</b>: {', '.join(result.get('authors', ['未知']))}</p>
                        <p><b>发布日期</b>: {result.get('published_date', '未知')}</p>
                        <p><b>摘要</b>: {result['snippet']}</p>
                        <a href="{result['url']}" target="_blank" style="color:#3498db;">查看原文 ↗</a>
                    </div>
                    """, unsafe_allow_html=True)
    
    with tab2:
        st.markdown("""
        <div style="background-color:#e8f4fc;padding:20px;border-radius:10px;margin-bottom:20px;">
            <h3 style="color:#2c3e50;margin:0;">高级分析选项</h3>
            <p style="color:#7f8c8d;">自定义提示词以获得更精确的分析结果</p>
        </div>
        """, unsafe_allow_html=True)
        
        custom_prompt = st.text_area("自定义提示词", height=200,
                                   value="请根据以下搜索结果撰写文献综述，重点关注方法论和研究空白:",
                                   help="输入自定义的提示词来指导AI分析")
        
        if st.button("使用自定义提示词运行", type="primary"):
            if not tavily_api_key or not deepseek_api_key:
                st.error("请提供Tavily和DeepSeek的API密钥")
                return
                
            if not topic:
                st.error("请输入研究主题")
                return
                
            safe_topic = re.sub(r'[\\/*?:"<>|]', "", topic)
            reviewer = AcademicPaperReviewer(tavily_api_key, deepseek_api_key)
            
            with st.status("正在处理...", expanded=True) as status:
                st.write("🔍 正在搜索学术文献...")
                search_results = reviewer.search_with_tavily(safe_topic, max_results)
                
                if not search_results:
                    status.update(label="处理完成 - 未找到结果", state="complete")
                    return
                
                st.write("🧠 正在使用自定义提示词分析...")
                combined_text = "\n\n".join([
                    f"标题: {r['title']}\n作者: {', '.join(r.get('authors', []))}\n摘要: {r['snippet']}"
                    for r in search_results
                ])
                
                output = reviewer._call_deepseek(custom_prompt, combined_text)
                status.update(label="处理完成!", state="complete")
            
            st.subheader("📊 自定义分析结果")
            st.markdown(output, unsafe_allow_html=True)

if __name__ == "__main__":
    if "run_review" not in st.session_state:
        st.session_state.run_review = False
    main()
