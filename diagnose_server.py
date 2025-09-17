#!/usr/bin/env python3
"""
服务器诊断工具 - 检查URL重定向和iframe问题
"""

import requests
import urllib.parse
import sys
import argparse
from urllib.parse import urljoin

def test_server_redirects(base_url):
    """测试服务器重定向行为"""
    print(f"🔍 测试服务器: {base_url}")
    print("=" * 50)

    test_paths = [
        "/",
        "//",  # 双斜杠根路径
        "/static//",  # 静态文件双斜杠
        "/static/nonexistent.html",  # 不存在的文件
    ]

    session = requests.Session()
    session.verify = False  # 忽略SSL证书警告

    for path in test_paths:
        test_url = urljoin(base_url, path)
        print(f"\n测试路径: {path}")
        print(f"完整URL: {test_url}")

        try:
            # 不自动跟随重定向
            response = session.get(test_url, allow_redirects=False, timeout=10)

            print(f"状态码: {response.status_code}")

            if response.status_code in [301, 302, 307, 308]:
                redirect_url = response.headers.get('Location', 'N/A')
                print(f"重定向: {response.status_code} → {redirect_url}")

                # 检查是否有双斜杠问题
                if '//' in redirect_url and not redirect_url.startswith(('http://', 'https://')):
                    print("❌ 发现双斜杠重定向问题!")
                else:
                    print("✅ 重定向路径正常")

                # 测试跟随重定向后的结果
                try:
                    final_response = session.get(test_url, allow_redirects=True, timeout=10)
                    print(f"最终状态: {final_response.status_code}")
                except Exception as e:
                    print(f"❌ 跟随重定向失败: {e}")

            elif response.status_code == 200:
                print("✅ 直接访问成功")
            elif response.status_code == 404:
                print("📄 页面不存在 (正常)")
            else:
                print(f"⚠️  其他状态: {response.status_code}")

        except requests.exceptions.SSLError as e:
            print(f"🔒 SSL错误: {e}")
            print("💡 尝试使用HTTP或添加--insecure参数")
        except requests.exceptions.ConnectionError as e:
            print(f"🔌 连接错误: {e}")
        except requests.exceptions.Timeout as e:
            print(f"⏱️  超时错误: {e}")
        except Exception as e:
            print(f"❌ 其他错误: {e}")

def test_iframe_accessibility(base_url):
    """测试iframe内容可访问性"""
    print(f"\n🖼️  测试iframe内容访问")
    print("=" * 50)

    # 模拟常见的iframe路径
    iframe_paths = [
        "/static/example/textured_mesh.html",
        "/static/example/white_mesh.html",
    ]

    session = requests.Session()
    session.verify = False

    for path in iframe_paths:
        test_url = urljoin(base_url, path)
        print(f"\n测试iframe路径: {path}")

        try:
            response = session.get(test_url, timeout=10)
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                # 检查内容类型
                content_type = response.headers.get('content-type', '')
                print(f"内容类型: {content_type}")

                # 检查是否包含模型查看器
                if 'model-viewer' in response.text:
                    print("✅ 包含3D模型查看器")
                else:
                    print("⚠️  未检测到3D模型查看器")

                # 检查安全头
                security_headers = [
                    'X-Frame-Options',
                    'Content-Security-Policy',
                    'X-Content-Type-Options'
                ]

                for header in security_headers:
                    value = response.headers.get(header)
                    if value:
                        print(f"安全头 {header}: {value}")
                    else:
                        print(f"⚠️  缺少安全头: {header}")

            else:
                print(f"❌ 访问失败: {response.status_code}")

        except Exception as e:
            print(f"❌ 错误: {e}")

def check_gradio_health(base_url):
    """检查Gradio应用健康状态"""
    print(f"\n🏥 检查Gradio应用健康状态")
    print("=" * 50)

    session = requests.Session()
    session.verify = False

    try:
        # 尝试访问根路径
        response = session.get(base_url, timeout=10)
        print(f"根路径状态: {response.status_code}")

        if response.status_code == 200:
            # 检查是否是Gradio应用
            if 'gradio' in response.text.lower():
                print("✅ Gradio应用正在运行")

                # 检查是否包含Hunyuan3D相关内容
                if any(keyword in response.text.lower() for keyword in ['hunyuan', '3d', 'model']):
                    print("✅ 检测到Hunyuan3D内容")
                else:
                    print("⚠️  未检测到Hunyuan3D相关内容")

                # 检查模型管理组件
                if 'model management' in response.text.lower() or 'load model' in response.text.lower():
                    print("✅ 检测到模型管理功能")
                else:
                    print("⚠️  未检测到模型管理功能")

            else:
                print("⚠️  不是Gradio应用或内容异常")

        else:
            print(f"❌ 应用无法访问: {response.status_code}")

    except Exception as e:
        print(f"❌ 健康检查失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="Hunyuan3D服务器诊断工具")
    parser.add_argument("url", help="服务器URL (例如: https://157.10.162.253)")
    parser.add_argument("--insecure", action="store_true", help="忽略SSL证书警告")

    args = parser.parse_args()

    base_url = args.url.rstrip('/')

    if args.insecure:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print("🔧 Hunyuan3D服务器诊断工具")
    print("=" * 60)

    # 运行各项检查
    test_server_redirects(base_url)
    check_gradio_health(base_url)
    test_iframe_accessibility(base_url)

    print("\n💡 修复建议:")
    print("- 如果发现307/双斜杠重定向问题，请重启服务器应用最新修复")
    print("- 如果SSL证书问题，请使用HTTP模式或配置有效证书")
    print("- 如果iframe无法显示，请检查浏览器控制台错误信息")

if __name__ == "__main__":
    main()