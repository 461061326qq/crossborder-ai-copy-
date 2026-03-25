# app.py - CrossBorder AI Copywriter Pro (降维打击版)
import streamlit as st
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import hashlib

load_dotenv()

# ==================== 配置区 ====================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
CREEM_API_KEY = os.getenv("CREEM_API_KEY", "")

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

PRICING = {
    "deepseek-chat": {"input": 0.5, "output": 8.0},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "qwen-turbo": {"input": 0.8, "output": 1.2}
}

MODEL_MAP = {
    "标准版 (快)": "deepseek-chat",
    "深度版 (优)": "deepseek-reasoner",
    "阿里云 (备)": "qwen-turbo"
}

SUBSCRIPTION_PLANS = {
    "free": {"price": 0, "copies_limit": 5, "models": ["deepseek-chat"]},
    "basic": {"price": 29, "copies_limit": 100, "models": ["deepseek-chat"]},
    "pro": {"price": 79, "copies_limit": 500, "models": ["deepseek-chat", "deepseek-reasoner"]},
    "enterprise": {"price": 199, "copies_limit": -1, "models": ["deepseek-chat", "deepseek-reasoner"]}
}

PLATFORM_TEMPLATES = {
    "Amazon": {"title_chars": (80, 200), "bullet_points": 5, "description_words": (150, 300), "search_terms": 15},
    "Shopify": {"title_chars": (50, 100), "bullet_points": 3, "description_words": (100, 200), "search_terms": 10},
    "eBay": {"title_chars": (55, 80), "bullet_points": 4, "description_words": (200, 400), "search_terms": 12},
    "Etsy": {"title_chars": (40, 140), "bullet_points": 3, "description_words": (100, 250), "search_terms": 13},
    "TikTok Shop": {"title_chars": (30, 60), "bullet_points": 3, "description_words": (50, 150), "search_terms": 8}
}

# ==================== 会话状态 ====================
if "brand_voice" not in st.session_state:
    st.session_state.brand_voice = {}
if "total_savings" not in st.session_state:
    st.session_state.total_savings = 0.0
if "copy_history" not in st.session_state:
    st.session_state.copy_history = []
if "user_subscription" not in st.session_state:
    st.session_state.user_subscription = "free"
if "copies_used" not in st.session_state:
    st.session_state.copies_used = 0
if "customer_email" not in st.session_state:
    st.session_state.customer_email = ""

# ==================== 支付功能 ====================
def create_creem_checkout_session(plan_id, price, customer_email):
    if not CREEM_API_KEY:
        return {"error": "Creem API Key未配置"}
    headers = {"Authorization": f"Bearer {CREEM_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "product_id": plan_id,
        "price": price,
        "currency": "USD",
        "customer_email": customer_email,
        "success_url": os.getenv("SUCCESS_URL", "https://yourdomain.com/success"),
        "cancel_url": os.getenv("CANCEL_URL", "https://yourdomain.com/cancel")
    }
    try:
        response = requests.post("https://api.creem.io/v1/checkout/sessions", headers=headers, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# ==================== AI生成功能 ====================
def calculate_cost(input_tokens, output_tokens, model):
    price = PRICING.get(model, PRICING["deepseek-chat"])
    input_cost = (input_tokens / 1_000_000) * price["input"]
    output_cost = (output_tokens / 1_000_000) * price["output"]
    return input_cost + output_cost

def generate_copywriting_deepseek(product_name, selling_points, platform, model, tone, competitor_copy=None):
    if not DEEPSEEK_API_KEY:
        return None, 0, 0, "⚠️ DeepSeek API Key未配置", None
    template = PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES["Amazon"])
    brand_context = ""
    voice_id = hashlib.md5(product_name.encode()).hexdigest()[:8]
    if voice_id in st.session_state.brand_voice:
        history = st.session_state.brand_voice[voice_id]
        if len(history.get("styles", [])) >= 2:
            brand_context = f"\n\nBrand style reference:\n---\n{history['styles'][-2][:500]}\n---"
    system_prompt = f"""You are a professional cross-border e-commerce copywriting expert for {platform}.
Platform Requirements:
- Title: {template['title_chars'][0]}-{template['title_chars'][1]} characters
- Bullet Points: {template['bullet_points']} points
- Description: {template['description_words'][0]}-{template['description_words'][1]} words
- Search Terms: {template['search_terms']} keywords
Writing Style: {tone}, Native English, Persuasive, SEO Optimized{brand_context}
Output Format:
## Title
[Your title here]
## Bullet Points
1. [Point 1]
2. [Point 2]
...
## Description
[Your description here]
## Search Terms
[keyword1, keyword2, ...]"""
    user_prompt = f"Product: {product_name}\nSelling Points:\n{selling_points}"
    if competitor_copy:
        user_prompt += f"\n\nCompetitor Copy to Beat:\n{competitor_copy}"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "temperature": 0.7,
        "max_tokens": 1500
    }
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = calculate_cost(input_tokens, output_tokens, model)
        return content, input_tokens + output_tokens, cost, "✅ 成功", None
    except Exception as e:
        return None, 0, 0, f"❌ API错误：{str(e)}", None

def generate_copywriting_dashscope(product_name, selling_points, platform, tone, competitor_copy=None):
    if not DASHSCOPE_API_KEY:
        return None, 0, 0, "⚠️ 阿里云API Key未配置", None
    template = PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES["Amazon"])
    prompt = f"""为{platform}平台生成电商文案：
产品：{product_name}
卖点：{selling_points}
要求：标题{template['title_chars'][0]}-{template['title_chars'][1]}字符，{template['bullet_points']}个卖点，描述{template['description_words'][0]}-{template['description_words'][1]}词
语调：{tone}"""
    if competitor_copy:
        prompt += f"\n竞品文案：{competitor_copy}"
    headers = {"Authorization": f"Bearer {DASHSCOPE_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "qwen-turbo", "input": {"prompt": prompt}, "parameters": {"temperature": 0.7}}
    try:
        response = requests.post(DASHSCOPE_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        content = result.get("output", {}).get("text", "")
        usage = result.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        cost = (total_tokens / 1_000_000) * PRICING["qwen-turbo"]["output"]
        return content, total_tokens, cost, "✅ 成功", None
    except Exception as e:
        return None, 0, 0, f"❌ API错误：{str(e)}", None

def analyze_competitor_copy(competitor_copy, platform):
    if not DEEPSEEK_API_KEY:
        return None
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": f"You are an e-commerce copywriting analyst for {platform}."},
            {"role": "user", "content": f"分析以下竞品文案的优缺点，给出改进建议：\n{competitor_copy}"}
        ],
        "temperature": 0.5,
        "max_tokens": 800
    }
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except:
        return None

def calculate_roi_estimates(platform, copy_length, tokens_used):
    base_ctr = {"Amazon": 0.5, "Shopify": 1.2, "Facebook Ads": 1.8, "Google Ads": 2.1, "TikTok Shop": 3.5, "eBay": 0.8, "Etsy": 1.0}
    avg_cpc = {"Amazon": 0.8, "Shopify": 1.2, "Facebook Ads": 1.5, "Google Ads": 2.0, "TikTok Shop": 0.6, "eBay": 0.5, "Etsy": 0.7}
    industry_avg = base_ctr.get(platform, 1.5)
    estimated_improvement = 25 + (tokens_used / 1000) * 5
    estimated_ctr = industry_avg * (1 + estimated_improvement / 100)
    monthly_clicks = 1000
    competitor_cost = monthly_clicks * avg_cpc.get(platform, 1.0)
    our_cost = competitor_cost * (1 - estimated_improvement / 100 / 2)
    savings = competitor_cost - our_cost
    return {
        "ctr_improvement": f"+{estimated_improvement:.1f}%",
        "estimated_ctr": f"{estimated_ctr:.2f}%",
        "monthly_savings": f"${savings:.2f}",
        "roi_score": min(100, 60 + estimated_improvement)
    }

def learn_brand_voice(product_name, generated_copy, user_feedback):
    voice_id = hashlib.md5(product_name.encode()).hexdigest()[:8]
    if voice_id not in st.session_state.brand_voice:
        st.session_state.brand_voice[voice_id] = {"products": [], "styles": [], "feedback_scores": []}
    st.session_state.brand_voice[voice_id]["products"].append(product_name)
    st.session_state.brand_voice[voice_id]["styles"].append(generated_copy[:500])
    st.session_state.brand_voice[voice_id]["feedback_scores"].append(user_feedback)
    return len(st.session_state.brand_voice[voice_id]["products"])

# ==================== Streamlit 界面 ====================
st.set_page_config(page_title="CrossBorder AI Copywriter Pro", page_icon="🚀", layout="wide")

st.markdown("""
<style>
.metric-card {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white;}
.roi-card {background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 20px; border-radius: 10px; color: white;}
.pricing-card {background: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);}
</style>
""", unsafe_allow_html=True)

st.sidebar.header("💵 成本优势")
st.sidebar.metric("我们的成本", f"¥{PRICING['deepseek-chat']['output']:.2f}/百万 tokens")
st.sidebar.metric("Jasper成本", "¥120.00/百万 tokens")
st.sidebar.metric("成本优势", "📉 93% 更低")
st.sidebar.markdown("---")
st.sidebar.header("📊 您的使用量")
plan = SUBSCRIPTION_PLANS.get(st.session_state.user_subscription, SUBSCRIPTION_PLANS["free"])
limit = "无限" if plan["copies_limit"] == -1 else plan["copies_limit"]
st.sidebar.metric("当前计划", st.session_state.user_subscription.upper())
st.sidebar.metric("已用文案", f"{st.session_state.copies_used}/{limit}")
st.sidebar.metric("累计节省", f"${st.session_state.total_savings:.2f}")

st.title("🚀 CrossBorder AI Copywriter Pro")
st.markdown("*AI-Powered • 90% Cost Reduction • ROI Tracked • 竞品拆解*")

api_status = []
if DEEPSEEK_API_KEY:
    api_status.append("✅ DeepSeek")
if DASHSCOPE_API_KEY:
    api_status.append("✅ 阿里云")
if not api_status:
    st.error("⚠️ 未配置任何AI API Key，请在环境变量中添加 DEEPSEEK_API_KEY 或 DASHSCOPE_API_KEY")
    st.stop()
else:
    st.sidebar.success("AI服务：" + " + ".join(api_status))

tab1, tab2, tab3, tab4 = st.tabs(["📝 文案生成", "🔍 竞品拆解", "📊 ROI看板", "💳 订阅计划"])

with tab1:
    if plan["copies_limit"] != -1 and st.session_state.copies_used >= plan["copies_limit"]:
        st.error("❌ 您已达到本月文案生成限额，请升级计划")
        st.stop()
    col1, col2, col3 = st.columns(3)
    with col1:
        product_name = st.text_input("产品名称", placeholder="e.g., Wireless Earbuds Pro")
        platform = st.selectbox("目标平台", list(PLATFORM_TEMPLATES.keys()))
    with col2:
        selling_points = st.text_area("核心卖点", placeholder="• 40 小时续航\n• 主动降噪\n• IPX7 防水", height=150)
    with col3:
        tone = st.selectbox("语调", ["professional", "friendly", "urgent", "luxury", "humorous"])
        model_choice = st.selectbox("AI模型", list(MODEL_MAP.keys()))
    competitor_copy = st.text_area("🥊 竞品文案（可选）", placeholder="粘贴竞品文案生成超越版本", height=100)
    if st.button("🎯 生成文案", type="primary", use_container_width=True):
        if not product_name or not selling_points:
            st.error("请填写产品名称和核心卖点")
        else:
            with st.spinner("🤖 AI 生成中..."):
                competitor_analysis = None
                if competitor_copy:
                    competitor_analysis = analyze_competitor_copy(competitor_copy, platform)
                    if competitor_analysis:
                        st.info("📝 **竞品分析**:\n" + competitor_analysis)
                model = MODEL_MAP.get(model_choice, "deepseek-chat")
                if model not in plan["models"]:
                    st.error(f"❌ 您的订阅计划不支持 {model_choice}，请升级")
                    st.stop()
                if "deepseek" in model:
                    content, tokens, cost, status, _ = generate_copywriting_deepseek(product_name, selling_points, platform, model, tone, competitor_copy if competitor_analysis else None)
                else:
                    content, tokens, cost, status, _ = generate_copywriting_dashscope(product_name, selling_points, platform, tone, competitor_copy if competitor_analysis else None)
                if content:
                    st.success("✅ 生成成功！")
                    st.markdown("### 📝 生成文案")
                    st.markdown(content)
                    roi_data = calculate_roi_estimates(platform, len(content), tokens)
                    if roi_data:
                        st.markdown("---")
                        st.markdown("### 📊 预计效果")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.markdown(f"<div class='roi-card'><b>CTR 提升</b><br>{roi_data['ctr_improvement']}</div>", unsafe_allow_html=True)
                        c2.markdown(f"<div class='roi-card'><b>预计 CTR</b><br>{roi_data['estimated_ctr']}</div>", unsafe_allow_html=True)
                        c3.markdown(f"<div class='roi-card'><b>月省广告费</b><br>{roi_data['monthly_savings']}</div>", unsafe_allow_html=True)
                        c4.markdown(f"<div class='roi-card'><b>ROI 评分</b><br>{roi_data['roi_score']}/100</div>", unsafe_allow_html=True)
                        st.session_state.total_savings += float(roi_data['monthly_savings'].replace('$', ''))
                    st.markdown("---")
                    cc1, cc2, cc3 = st.columns(3)
                    cc1.metric("Token 消耗", f"{tokens:,}")
                    cc2.metric("本次成本", f"¥{cost:.6f}")
                    cc3.metric("竞品等效成本", f"¥{cost * 15:.6f}")
                    st.session_state.copies_used += 1
                    feedback = st.selectbox("🎯 符合品牌声音吗？", ["非常满意", "满意", "一般", "需要改进"])
                    if st.button("💾 保存到品牌声音"):
                        learn_brand_voice(product_name, content, feedback)
                        st.session_state.copy_history.append({"产品": product_name, "日期": datetime.now().strftime("%Y-%m-%d"), "反馈": feedback, "平台": platform})
                        st.success("✅ 已保存！")
                    st.download_button(label="📥 下载文案", data=content, file_name=f"{product_name}_copy.txt", mime="text/plain")
                else:
                    st.error(status)

with tab2:
    st.markdown("### 🔍 竞品文案拆解")
    st.info("💡 粘贴竞品文案，AI自动分析优缺点并给出超越方案")
    competitor_copy_tab2 = st.text_area("竞品文案", placeholder="粘贴竞品标题、卖点、描述", height=200)
    platform_tab2 = st.selectbox("目标平台", list(PLATFORM_TEMPLATES.keys()), key="tab2_platform")
    if st.button("🔬 分析竞品", use_container_width=True):
        if not competitor_copy_tab2:
            st.error("请粘贴竞品文案")
        else:
            with st.spinner("🔍 分析中..."):
                analysis = analyze_competitor_copy(competitor_copy_tab2, platform_tab2)
                if analysis:
                    st.markdown("### 📝 分析报告")
                    st.markdown(analysis)

with tab3:
    st.markdown("### 📊 ROI 看板")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='metric-card'><b>累计节省</b><br>${st.session_state.total_savings:.2f}</div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><b>已生成文案</b><br>{st.session_state.copies_used} 篇</div>", unsafe_allow_html=True)
    avg = st.session_state.total_savings / max(1, st.session_state.copies_used)
    c3.markdown(f"<div class='metric-card'><b>平均节省/篇</b><br>${avg:.2f}</div>", unsafe_allow_html=True)
    if st.session_state.copy_history:
        st.markdown("### 📝 生成历史")
        st.dataframe(st.session_state.copy_history, use_container_width=True)

with tab4:
    st.markdown("### 💳 选择订阅计划")
    st.info("🎉 新用户免费 5 篇文案，无需信用卡")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class='pricing-card'>
        ### 基础版
        ## $29/月
        - 100 篇文案/月
        - DeepSeek 标准模型
        - 基础 ROI 追踪
        </div>
        """, unsafe_allow_html=True)
        if st.button("订阅基础版", key="basic", use_container_width=True):
            if not st.session_state.customer_email:
                st.session_state.customer_email = st.text_input("您的邮箱", key="basic_email_input")
            if st.session_state.customer_email:
                session = create_creem_checkout_session("basic_plan", 29, st.session_state.customer_email)
                if "checkout_url" in session:
                    st.markdown(f"[👉 点击完成支付]({session['checkout_url']})")
                else:
                    st.error(f"创建支付会话失败：{session.get('error', '未知错误')}")
    with col2:
        st.markdown("""
        <div class='pricing-card' style='border: 2px solid #667eea;'>
        ### 专业版 ⭐
        ## $79/月
        - 500 篇文案/月
        - DeepSeek 深度模型
        - 竞品分析功能
        - 品牌声音记忆
        </div>
        """, unsafe_allow_html=True)
        if st.button("订阅专业版", key="pro", use_container_width=True):
            if not st.session_state.customer_email:
                st.session_state.customer_email = st.text_input("您的邮箱", key="pro_email_input")
            if st.session_state.customer_email:
                session = create_creem_checkout_session("pro_plan", 79, st.session_state.customer_email)
                if "checkout_url" in session:
                    st.markdown(f"[👉 点击完成支付]({session['checkout_url']})")
                else:
                    st.error(f"创建支付会话失败：{session.get('error', '未知错误')}")
    with col3:
        st.markdown("""
        <div class='pricing-card'>
        ### 企业版
        ## $199/月
        - 无限文案
        - 所有AI模型
        - API 访问
        - 定制集成
        </div>
        """, unsafe_allow_html=True)
        if st.button("订阅企业版", key="enterprise", use_container_width=True):
            if not st.session_state.customer_email:
                st.session_state.customer_email = st.text_input("您的邮箱", key="enterprise_email_input")
            if st.session_state.customer_email:
                session = create_creem_checkout_session("enterprise_plan", 199, st.session_state.customer_email)
                if "checkout_url" in session:
                    st.markdown(f"[👉 点击完成支付]({session['checkout_url']})")
                else:
                    st.error(f"创建支付会话失败：{session.get('error', '未知错误')}")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'><small>🔒 数据不存储 • 2026 CrossBorder AI Inc.</small></div>", unsafe_allow_html=True)