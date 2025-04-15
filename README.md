# 文献转流程图工具

这是一个基于Streamlit的Web应用程序，可以将文本或PDF文件中的流程描述转换为可视化的流程图。

## 功能特点

- 支持批量上传TXT和PDF文件
- 使用DeepSeek API自动生成Mermaid流程图代码
- 可选生成中文摘要
- 自动将流程图导出为PNG格式
- 支持批量下载所有生成结果（ZIP格式）

## 安装要求

1. Python 3.8+
2. Node.js 和 npm（用于mermaid-cli）

## 安装步骤

1. 克隆仓库：

```bash
git clone https://github.com/[你的用户名]/literature-flowchart.git
cd literature-flowchart
```

2. 安装Python依赖：

```bash
pip install -r requirements.txt
```

3. 安装mermaid-cli：

```bash
npm install -g @mermaid-js/mermaid-cli
```

## 使用方法

1. 运行Streamlit应用：

```bash
streamlit run streamlit_run.py
```

2. 在浏览器中打开显示的URL（通常是 http://localhost:8501）

3. 在侧边栏中输入你的DeepSeek API密钥

4. 上传TXT或PDF文件，选择是否需要生成中文摘要

5. 点击"批量生成流程图"按钮

6. 处理完成后，可以下载包含所有结果的ZIP文件

## 注意事项

- 请确保有可用的DeepSeek API密钥
- 确保文本描述清晰准确以获得最佳的流程图效果
- PDF文件需要是可提取文本的格式

## 在线演示

你可以在Streamlit Cloud上访问该应用：
[应用链接将在部署后更新]

## License
