"""检查所有服务状态"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx


async def check_services():
    print('\n' + '=' * 80)
    print('服务状态检查')
    print('=' * 80)
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        # 检查后端
        print('\n[1/3] 检查后端服务 (http://localhost:8000)')
        try:
            response = await client.get('http://localhost:8000/api/health')
            if response.status_code == 200:
                print('  ✓ 后端服务正常')
                print(f'    响应：{response.json()}')
            else:
                print(f'  ✗ 后端服务异常 (状态码：{response.status_code})')
        except Exception as e:
            print(f'  ✗ 后端服务无法连接：{e}')
        
        # 检查 Web 管理端
        print('\n[2/3] 检查 Web 管理端 (http://localhost:3000)')
        try:
            response = await client.get('http://localhost:3000')
            if response.status_code == 200:
                print('  ✓ Web 管理端正常')
            else:
                print(f'  ✗ Web 管理端异常 (状态码：{response.status_code})')
        except Exception as e:
            print(f'  ✗ Web 管理端无法连接：{e}')
        
        # 检查 H5 移动端
        print('\n[3/3] 检查 H5 移动端 (http://localhost:5174)')
        try:
            response = await client.get('http://localhost:5174')
            if response.status_code == 200:
                print('  ✓ H5 移动端正常')
            else:
                print(f'  ✗ H5 移动端异常 (状态码：{response.status_code})')
        except Exception as e:
            print(f'  ✗ H5 移动端无法连接：{e}')
        
        # 测试登录
        print('\n[4/4] 测试登录功能')
        try:
            response = await client.post(
                'http://localhost:8000/api/auth/login',
                json={'username': 'admin', 'password': 'admin123'}
            )
            if response.status_code == 200:
                data = response.json()
                print('  ✓ 登录功能正常')
                print(f'    用户：{data["data"]["user"]["username"]}')
                print(f'    Token: {data["data"]["access_token"][:50]}...')
            else:
                print(f'  ✗ 登录功能异常 (状态码：{response.status_code})')
                print(f'    错误：{response.json().get("detail", "Unknown")}')
        except Exception as e:
            print(f'  ✗ 登录功能无法测试：{e}')
    
    print('\n' + '=' * 80)


if __name__ == '__main__':
    asyncio.run(check_services())
