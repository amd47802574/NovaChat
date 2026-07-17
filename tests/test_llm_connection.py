"""
大模型连接测试脚本 - 验证大模型是否可用
运行方式：python tests/test_llm_connection.py

测试内容：
1. 环境变量配置检查
2. 基本对话能力测试
3. 流式输出测试
4. Token计数测试
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    print("提示：安装 python-dotenv 可以自动加载 .env 文件")

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check_environment_variables():
    """检查必要的环境变量配置"""
    print_section("1. 环境变量检查")
    
    # Load .env file if exists
    env_file = project_root / ".env"
    if env_file.exists() and HAS_DOTENV:
        load_dotenv(env_file)
        print(f"✓ 已加载 .env 文件：{env_file}")
    elif env_file.exists():
        print(f"⚠ .env 文件存在但未自动加载（缺少 python-dotenv）")
    else:
        print(f"⚠ 未找到 .env 文件：{env_file}")
    
    # Check required variables
    required_vars = {
        "ARK_API_KEY": "API密钥",
        "MODEL": "模型名称",
        "BASE_URL": "API地址"
    }
    
    all_set = True
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive information
            display_value = value[:10] + "..." if len(value) > 10 else value
            print(f"✓ {desc} ({var}): {display_value}")
        else:
            print(f"✗ {desc} ({var}): 未设置")
            all_set = False
    
    return all_set


def test_basic_chat():
    """测试基本对话能力"""
    print_section("2. 基本对话能力测试")
    
    try:
        # Initialize model
        print("正在初始化模型...")
        model = init_chat_model(
            model=os.getenv("MODEL"),
            model_provider="openai",
            api_key=os.getenv("ARK_API_KEY"),
            base_url=os.getenv("BASE_URL"),
            temperature=0.7,
        )
        print("✓ 模型初始化成功")
        
        # Test basic conversation
        print("\n发送测试消息：'你好，请用一句话介绍你自己'")
        response = model.invoke([
            SystemMessage(content="你是一个友好的助手"),
            HumanMessage(content="你好，请用一句话介绍你自己")
        ])
        
        print(f"\n模型回复：\n{response.content}")
        print(f"\n✓ 基本对话测试通过")
        
        # Check token usage
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            print(f"\nToken 使用情况：")
            print(f"  - 输入 tokens: {response.usage_metadata.get('input_tokens', 'N/A')}")
            print(f"  - 输出 tokens: {response.usage_metadata.get('output_tokens', 'N/A')}")
            print(f"  - 总计 tokens: {response.usage_metadata.get('total_tokens', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 基本对话测试失败：{str(e)}")
        return False


def test_streaming():
    """测试流式输出"""
    print_section("3. 流式输出测试")
    
    try:
        # Initialize model with streaming
        print("正在初始化流式模型...")
        model = init_chat_model(
            model=os.getenv("MODEL"),
            model_provider="openai",
            api_key=os.getenv("ARK_API_KEY"),
            base_url=os.getenv("BASE_URL"),
            temperature=0.7,
        )
        print("✓ 流式模型初始化成功")
        
        # Test streaming
        print("\n发送流式测试消息：'请写一首关于AI的短诗'")
        print("\n模型回复（流式）：")
        
        stream = model.stream([
            SystemMessage(content="你是一个诗人"),
            HumanMessage(content="请写一首关于AI的短诗")
        ])
        
        full_response = ""
        token_count = 0
        for chunk in stream:
            if chunk.content:
                print(chunk.content, end="", flush=True)
                full_response += chunk.content
                token_count += 1
        
        print(f"\n\n✓ 流式输出测试通过")
        print(f"流式 chunk 数量：{token_count}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 流式输出测试失败：{str(e)}")
        return False


def test_fast_model():
    """测试快速模型（如果配置）"""
    print_section("4. 快速模型测试")
    
    fast_model = os.getenv("FAST_MODEL") or os.getenv("MODEL")
    
    if not fast_model:
        print("⚠ 未配置 FAST_MODEL，跳过测试")
        return True
    
    try:
        print(f"正在测试快速模型：{fast_model}")
        model = init_chat_model(
            model=fast_model,
            model_provider="openai",
            api_key=os.getenv("ARK_API_KEY"),
            base_url=os.getenv("BASE_URL"),
            temperature=0.3,
        )
        
        print("✓ 快速模型初始化成功")
        
        # Test with simple question
        response = model.invoke([
            HumanMessage(content="1+1等于几？")
        ])
        
        print(f"快速模型回复：{response.content}")
        print("✓ 快速模型测试通过")
        
        return True
        
    except Exception as e:
        print(f"✗ 快速模型测试失败：{str(e)}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  NovaChat 大模型连接测试")
    print("="*60)
    
    results = []
    
    # Test 1: Environment variables
    env_ok = check_environment_variables()
    results.append(("环境变量检查", env_ok))
    
    if not env_ok:
        print("\n⚠ 环境变量配置不完整，无法继续测试")
        print("\n请确保已设置以下环境变量：")
        print("  - ARK_API_KEY: API密钥")
        print("  - MODEL: 模型名称")
        print("  - BASE_URL: API地址")
        print("\n或在项目根目录创建 .env 文件（参考 .env.example）")
        return
    
    # Test 2: Basic chat
    basic_ok = test_basic_chat()
    results.append(("基本对话能力", basic_ok))
    
    # Test 3: Streaming
    if basic_ok:
        streaming_ok = test_streaming()
        results.append(("流式输出能力", streaming_ok))
    else:
        results.append(("流式输出能力", False))
    
    # Test 4: Fast model
    fast_ok = test_fast_model()
    results.append(("快速模型测试", fast_ok))
    
    # Summary
    print_section("测试结果汇总")
    
    for test_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n测试完成：{passed}/{total} 项测试通过")
    
    if passed == total:
        print("\n🎉 大模型连接正常，可以正常使用！")
    else:
        print(f"\n⚠ {total - passed} 项测试失败，请检查配置或网络连接")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()