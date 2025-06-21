import requests
import json
from pprint import pprint

def test_search_api():
    # 测试服务器地址
    base_url = "http://localhost:12347"
    
    # 测试用例
    test_cases = [
        {
            "params": {
                "search": "",
                "priority": "",
                "status": "",
                "tag": ""
            },
            "description": "测试空查询"
        },
        {
            "params": {
                "search": "测试",
                "priority": "",
                "status": "",
                "tag": ""
            },
            "description": "测试中文关键词搜索"
        },
        {
            "params": {
                "search": "",
                "priority": "高",
                "status": "",
                "tag": ""
            },
            "description": "测试优先级过滤"
        },
        {
            "params": {
                "search": "",
                "priority": "",
                "status": "未完成",
                "tag": ""
            },
            "description": "测试状态过滤"
        },
        {
            "params": {
                "search": "",
                "priority": "",
                "status": "",
                "tag": "工作"
            },
            "description": "测试标签过滤"
        },
        {
            "params": {
                "search": "测试",
                "priority": "高",
                "status": "未完成",
                "tag": "工作"
            },
            "description": "测试组合过滤"
        }
    ]
    
    print("开始测试搜索接口...\n")
    
    for test_case in test_cases:
        print(f"\n测试用例: {test_case['description']}")
        print(f"查询参数: {test_case['params']}")
        
        try:
            # 发送GET请求到搜索接口
            response = requests.get(
                f"{base_url}/search",
                params=test_case["params"]
            )
            
            # 检查响应状态码
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                # 尝试解析JSON响应
                try:
                    data = response.json()
                    print("\n返回数据:")
                    print(f"数据条数: {len(data)}")
                    if data:
                        print("\n第一条数据示例:")
                        pprint(data[0])
                except json.JSONDecodeError:
                    print("错误: 返回的数据不是有效的JSON格式")
                    print("原始响应:", response.text)
            else:
                print(f"错误: 请求失败，状态码 {response.status_code}")
                print("响应内容:", response.text)
                
        except requests.exceptions.ConnectionError:
            print("错误: 无法连接到服务器，请确保服务器正在运行")
        except Exception as e:
            print(f"错误: {str(e)}")
        
        print("-" * 50)

if __name__ == "__main__":
    test_search_api() 