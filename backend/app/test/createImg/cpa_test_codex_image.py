import requests
import base64
from datetime import datetime
import os

# ==================== 配置 ====================
API_BASE_URL = "http://43.128.147.93:8317/v1"
API_KEY = "sk-xiaoleai"
REQUEST_TIMEOUT = 600

# 创建保存目录
SAVE_DIR = "generated_images"
os.makedirs(SAVE_DIR, exist_ok=True)


def generate_images(
    prompt: str,
    n: int = 1,
    size: str = "1024x1792",
    quality: str = "high",
    timeout: int = REQUEST_TIMEOUT,
):
    """
    调用 gpt-image-2 生成图片并保存到本地
    """
    url = f"{API_BASE_URL}/images/generations"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-image-2",
        "prompt": prompt,
        "n": n,
        "size": size,
        "quality": quality,
        "response_format": "b64_json"
    }

    print(f"🚀 开始生成 {n} 张图片，比例 {size}，超时 {timeout} 秒...")
    try:
        response = requests.post(url, headers=headers, json=data, timeout=timeout)
    except requests.exceptions.ReadTimeout:
        print(f"❌ 请求超时，已等待 {timeout} 秒仍未返回结果")
        return None

    if response.status_code == 200:
        result = response.json()
        if "data" in result and len(result["data"]) > 0:
            print(f"✅ API 返回成功，共 {len(result['data'])} 张图片")
            for i, item in enumerate(result["data"], 1):
                b64_data = item.get("b64_json", "")
                b64_preview = b64_data[:50] + "..." if b64_data else "无数据"
                print(f"   图片 {i}: base64 长度 {len(b64_data)} 字符，预览: {b64_preview}")


        if "data" in result and len(result["data"]) > 0:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            saved_files = []

            for i, item in enumerate(result["data"], 1):
                try:
                    b64_data = item["b64_json"]
                    image_data = base64.b64decode(b64_data)

                    filename = f"{SAVE_DIR}/gptimage_{size.replace('x', '_')}_{timestamp}_{i:02d}.png"

                    with open(filename, "wb") as f:
                        f.write(image_data)

                    saved_files.append(filename)
                    print(f"✅ 第 {i}/{n} 张保存完成: {filename}")

                except Exception as e:
                    print(f"❌ 保存第 {i} 张图片失败: {e}")

            print(f"\n🎉 全部完成！共保存 {len(saved_files)} 张图片")
            return saved_files
        else:
            print("⚠️ 返回数据中没有图片")
            return None
    else:
        print(f"❌ 请求失败 ({response.status_code})")
        print(response.text)
        return None


if __name__ == "__main__":
    # ==================== 测试调用 ====================
    prompt = """
    根据下列描述生成一个logo:
    小乐AI中转站（AI 模型调用中转系统）是一个多层级、全功能的 AI 接口分发与管理平台。它主要的作用是向下游用户或开发者提供统一的 AI 模型 API 调用服务，并进行计费、渠道路由和额度控制。

以下是系统的核心业务逻辑与主要功能模块描述：

一、核心业务机制

模型分发与路由：系统作为统一网关（Gateway），对接上游多种大模型（如 GPT、Claude 等）的底层渠道（Channels），并将其整合后提供给下游调用。
多级角色架构：系统分为“管理员（平台方）”、“代理商”和“普通用户”三个层级，支持代理商独立运营自己的客户群体。
额度与计费控制：通过令牌（Tokens）或固定套餐计算用户调用大模型所消耗的算力资产。
二、主要功能模块（按角色划分）

【1】管理员端（Admin）—— 平台最高权限

渠道与模型管理：配置上游 API 渠道（API Key、代理池等），管理系统中可供调用的模型列表及模型倍率定价。
代理与分销管理：管理下级代理商账号，处理代理商的资产充值、额度分配与资金结算。
财务与商品配置：生成并分发兑换码（充值卡），配置订阅套餐方案。
系统全局监控：查看系统健康状态、全局请求日志分析、全站用户的调用量排行及系统基础参数配置。
用户管理：拥有查看和管理全站所有用户的最高权限。
【2】代理端（Agent）—— 独立运营者

客户管理：管理通过自己专属链接或邀请码注册的直属用户，查看其状态并进行额度管控。
财务与商品运营：在自己的额度池内，生成专属的充值兑换码，或配置属于自己客户的订阅套餐方案。
运营分析：通过专属工作台和数据看板，查看名下客户的请求记录、API 调用消耗日志以及用户的调用排行，从而制定运营策略。
【3】普通用户端（User）—— 终端消费者

AI 对话体验：内置了网页端和手机端自适应的 AI 聊天界面，供用户直接体验大模型能力。
API 密钥管理：生成和管理自己的 API Key，以便将中转服务集成到第三方软件或自己的代码中。
额度与账单追踪：查看详尽的账单流水、额度消耗统计图表以及自身的使用量排行。
充值与消费：使用代理或管理员发放的兑换码进行额度充值，或购买订阅套餐。
快速开发：提供模型列表查看功能及“快速开始”指南，帮助开发者快速接入 API。
整体而言，这是一个集成了“API 聚合路由、多级分销代理、精细化额度计费以及直接对话 UI”的综合性 AI 商业化落地系统。
    """
    # 生成 1 张竖屏图片（9:16）
    generate_images(prompt, n=1, size="3840x2160")
