#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eteams 连接客户端 - Python 实现

实现功能：
1. RSA 密码加密
2. 用户登录获取 eteamsid
3. eteams WebSocket 连接
4. 心跳保持
5. IM Token 获取
6. IM WebSocket 连接
"""

import base64
import json
import time
import random
import string
import asyncio
import urllib.parse
import uuid as uuid_lib
from typing import Optional, Dict, Any
from dataclasses import dataclass

import requests
# from Crypto.PublicKey import RSA
# from Crypto.Cipher import PKCS1_v1_5
import websockets
from websockets.client import WebSocketClientProtocol


@dataclass
class LoginConfig:
    """登录配置"""
    base_url: str  # 服务器地址，如: http://www.guangzh.cr
    phone: str  # 手机号
    password: str  # 明文密码
    device_type: int = 9  # 设备类型: 9=Windows, 7=Mac, 8=Linux


@dataclass
class UserInfo:
    """用户信息"""
    user_id: str
    emp_id: str
    tenant_key: str
    eteams_id: str
    eteamsid: str  # 会话令牌
    company_id: str


class EteamsClient:
    """eteams 客户端"""

    def __init__(self, config: LoginConfig):
        self.config = config
        self.session = requests.Session()
        self.user_info: Optional[UserInfo] = None
        self.eteams_ws: Optional[WebSocketClientProtocol] = None
        self.im_ws: Optional[WebSocketClientProtocol] = None
        self._running = False
        self._heartbeat_task = None
        self.eteams_conn_id: Optional[str] = None  # 服务器返回的 connId
        self.server_wicket: Optional[str] = None  # 从服务器获取的 wicket
        self.im_seq_counter = 10000  # IM 消息序列号计数器（从10000开始）
        self.im_seq_lock = asyncio.Lock()  # 序列号锁
        self.message_callbacks = []  # 消息回调列表
        self._message_senders: dict[str, str] = {}  # msg_id -> sender_uid 映射

    def _get_kind_name(self, kind: str) -> str:
        """
        获取消息类型名称

        Args:
            kind: 消息类型代码

        Returns:
            消息类型名称
        """
        kind_map = {
            '1001': '系统消息',
            '1002': '文本消息',
            '1003': '图片消息',
            '1004': '语音消息',
            '1005': '文件消息',
            '1006': '视频消息',
            '1007': '链接消息',
            '1008': '位置消息',
            '1009': '表情消息',
            '1010': '群聊消息',
            '1011': '撤回消息',
            '1012': '引用消息',
            '1013': '转发消息',
            '1014': '卡片消息',
            '1015': '富文本消息',
        }
        return kind_map.get(str(kind), f'未知类型({kind})')

    def _get_full_url(self, path: str) -> str:
        """获取完整的 URL"""
        base = self.config.base_url.rstrip('/')
        path = path.lstrip('/')
        return f"{base}/{path}"

    def _get_im_seq(self) -> str:
        """
        获取下一个 IM 消息序列号

        Returns:
            序列号字符串
        """
        self.im_seq_counter += 1
        return str(self.im_seq_counter)

    async def _get_im_seq_async(self) -> str:
        """
        异步获取下一个 IM 消息序列号（线程安全）

        Returns:
            序列号字符串
        """
        async with self.im_seq_lock:
            self.im_seq_counter += 1
            return str(self.im_seq_counter)

    def register_message_callback(self, callback):
        """
        注册消息回调函数

        Args:
            callback: 回调函数，可以是同步或异步函数
                     接收一个参数: message_data (dict)
                     message_data 包含:
                     - msg_id: 消息ID
                     - msg_type: 消息类型
                     - sender_name: 发送者名称
                     - sender_uid: 发送者用户ID
                     - content: 消息内容（文本）
                     - raw_data: 原始消息数据
        """
        self.message_callbacks.append(callback)

    async def _notify_message(self, message_data: dict):
        """
        通知所有注册的回调函数

        Args:
            message_data: 消息数据字典
        """
        for callback in self.message_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message_data)
                else:
                    callback(message_data)
            except Exception as e:
                print(f"[ERROR] 回调执行失败: {e}")

    def get_sys_config(self) -> Dict[str, Any]:
        """
        获取系统配置（包含 RSA 公钥）

        Returns:
            系统配置字典
        """
        url = self._get_full_url('/papi/em/base/getSysConfig')
        params = {'devType': self.config.device_type}

        response = self.session.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        if data.get('code') != '1':
            raise Exception(f"获取系统配置失败: {data.get('msg', 'Unknown error')}")

        return data.get('data', {})

    def mobile_login(self, encrypted_password: str) -> Dict[str, Any]:
        """
        手机号密码登录

        Args:
            encrypted_password: RSA 加密后的密码

        Returns:
            登录响应数据
        """
        url = self._get_full_url('/papi/secdev/portal/login/mobileLogin')

        # URL 编码加密后的密码
        # encoded_password = urllib.parse.quote(encrypted_password)

        # 构造表单数据
        form_data = {
            'loginid': self.config.phone,
            'password': encrypted_password
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        print(form_data)
        response = self.session.post(url, data=form_data, headers=headers)
        response.raise_for_status()
        print(response.text)
        data = response.json()
        if data.get('msgcode') != '0':
            raise Exception(f"登录失败: {data.get('msg', 'Unknown error')}")
        print(f"Cookies: {dict(self.session.cookies)}")

        send_url = data.get('sendUrl', "")
        print(send_url)
        # self.session.get(send_url)
        print(f"Cookies: {dict(self.session.cookies)}")

        return data.get('access_token', "")

    def single_signon(self, single_token: str) -> None:
        """
        SSO 单点登录

        Args:
            single_token: 单点登录令牌
        """
        # http://www.guangzh.cr/papi/open/singleSignon?singleToken=ab2f5b80335d6648184f160e78157ed2&oauthType=singlesign&redirect_uri=http://www.guangzh.cr
        url = self._get_full_url('/papi/open/singleSignon')
        headers = {
            'Content-Type': 'multipart/form-data',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.80 Electron/41.0.3 Safari/537.36 weapp-pc/10.1.16/eteams-desktop'
        }
        params = {
            'singleToken': single_token,
            'oauthType': 'singlesign',
            'redirect_uri': self.config.base_url
        }
        print(params)
        response = self.session.get(url, params=params,)
        response.raise_for_status()
        print(response.status_code)
        print(response.text)

        print(f"Cookies: {dict(response.cookies)}")
        print(f"Cookies: {dict(self.session.cookies)}")

    def get_init_info(self) -> Dict[str, Any]:
        """
        获取初始化信息（用户信息）

        Returns:
            用户信息字典
        """
        url = self._get_full_url(
            '/api/em/base/getInitInfo?devType=9&isConfig=1&isSysConfig=1&isTeamConfig=1&getTime=1773903579683&randomkey_34m599=7t9ob')

        response = self.session.get(url)
        response.raise_for_status()

        data = response.json()
        print(data)
        if data.get('code') != 200:
            raise Exception(f"获取初始化信息失败: {data.get('msg', 'Unknown error')}")

        return data.get('data', {})

    def _im_send(self, toUser: str,  content: str):
        """
        发送消息
        Args:
            toUser (str): _description_
            content (str): _description_

        Raises:
            Exception: _description_
        """
        headers = {
            'Content-Type': 'application/json',
            # 'Cookie': 'eteamsid=' + self.user_info.eteams_id
        }
        payload = {
            'to': toUser,
            'type': 'text',
            'content': content,
            'sessionType': 1,
            'sessionId': ''
        }
        response = self.session.post(
            'http://www.guangzh.cr/api/im/send', json=payload, headers=headers)
        im_send_result = response.json()
        if im_send_result.get('code') != 200:
            raise Exception(
                f"发送消息失败: {im_send_result.get('msg', 'Unknown error')}")

        print("_im_send return: {im_send_result}")

    def extract_eteamsid(self) -> str:
        """
        从会话 Cookie 中提取 eteamsid

        Returns:
            eteamsid 字符串
        """
        for cookie in self.session.cookies:
            if cookie.name == 'ETEAMSID':
                return cookie.value
        raise Exception("未找到 eteamsid Cookie")

    def login(self) -> UserInfo:
        """
        完整登录流程

        Returns:
            用户信息
        """
        print("=" * 60)
        print("开始登录流程...")
        print("=" * 60)

        encrypted_password = "So3j53+KRjM5RboyW2GP2GVgINwAWd7WuiEQXdQUEsrbiwle0PGyTzFUQUnGIOPcdwGHsm0xI05krqhC786rRtJ9cr5f679Y8jeiPuQN3FQHNyqrzet1FY5XSb4s3q86tvCtglfqur98ueqcJmpjC0HmK6dBSjOZcLv6mRC6IEY="
        # 3. 登录
        print("\n[3/5] 发送登录请求...")
        access_token = self.mobile_login(encrypted_password)
        print(f"  登录成功")

        self.single_signon(access_token)

        # 4. 提取 eteamsid
        print("\n[4/5] 提取 eteamsid...")
        eteamsid = self.extract_eteamsid()
        print(f"  eteamsid: {eteamsid[:16]}...")

        # 5. 获取用户信息
        print("\n[5/5] 获取用户信息...")
        init_info = self.get_init_info()
        # 打印完整配置用于调试
        print(f"\n[DEBUG] init_info keys: {init_info.keys()}")

        # 打印所有可能的配置位置
        sys_config = init_info.get('sysConfig', {})
        team_config = init_info.get('teamConfig', {})
        user_data = init_info.get('user', {})

        print(
            f"[DEBUG] sysConfig: {json.dumps(sys_config, ensure_ascii=False)[:500]}")
        print(
            f"[DEBUG] teamConfig: {json.dumps(team_config, ensure_ascii=False)[:500]}")
        print(
            f"[DEBUG] user_data: {json.dumps(user_data, ensure_ascii=False)[:500]}")

        # 提取 wicket 等配置
        self.server_wicket = sys_config.get(
            'wicket', '') or team_config.get('wicket', '')
        if self.server_wicket:
            print(f"[DEBUG] 从服务器获取到 wicket: {self.server_wicket}")
        else:
            print("[DEBUG] 未从服务器获取到 wicket，将使用默认值")

        # 解析用户信息
        user_data = init_info.get('user', {})
        print(
            f"[DEBUG] user_data keys: {user_data.keys() if user_data else 'None'}")
        print(
            f"[DEBUG] user_data: {json.dumps(user_data, ensure_ascii=False)[:500]}")

        # 尝试从多个位置获取 tenantKey
        tenant_key = user_data.get('tenantKey') or init_info.get(
            'tenantKey') or 'all_teams'
        print(f"[DEBUG] tenant_key: {tenant_key}")

        self.user_info = UserInfo(
            user_id=user_data.get('id', ''),
            emp_id=user_data.get('empId', ''),
            tenant_key=tenant_key,  # 使用提取的 tenant_key
            eteams_id=eteamsid,
            eteamsid=eteamsid,
            company_id=user_data.get('companyId', '')
        )

        print(f"  用户ID: {self.user_info.user_id}")
        print(f"  员工ID: {self.user_info.emp_id}")
        print(f"  租户键: {self.user_info.tenant_key}")
        print(f"  eteamsId: {self.user_info.eteams_id}")

        print("\n" + "=" * 60)
        print("登录完成！")
        print("=" * 60)

        return self.user_info

    def get_eteams_ws_url(self) -> str:
        """
        构造 eteams WebSocket 连接 URL

        Returns:
            WebSocket URL
        """
        # Base64 编码用户ID和员工ID
        user_id_b64 = base64.b64encode(
            self.user_info.user_id.encode()).decode()
        emp_id_b64 = base64.b64encode(self.user_info.emp_id.encode()).decode()

        # 生成随机数
        random_str = ''.join(random.choices(
            string.ascii_lowercase + string.digits, k=10))
        ran = f"{random_str}_{int(time.time() * 1000)}"

        # 构造 URL
        ws_url = self.config.base_url.replace(
            'http://', 'ws://').replace('https://', 'wss://')
        ws_url = f"{ws_url}/api/online/webSocket"
        ws_url += f"?dtu=app-pc"
        ws_url += f"&userId={user_id_b64}"
        ws_url += f"&ran={ran}"
        ws_url += f"&empId={emp_id_b64}"

        return ws_url

    async def connect_eteams_websocket(self) -> None:
        """
        连接 eteams WebSocket
        """
        if not self.user_info:
            raise Exception("请先登录")

        ws_url = self.get_eteams_ws_url()
        print(f"\n连接 eteams WebSocket: {ws_url}")

        headers = {
            'Cookie': f'ETEAMSID={self.user_info.eteamsid}'
        }
        self.eteams_ws = await websockets.connect(ws_url, additional_headers=headers)
        print("eteams WebSocket 连接成功！")

        # 先启动消息接收循环（在后台运行）
        # 注意：注册消息会在收到 connSucc 后自动发送
        asyncio.create_task(self._eteams_message_loop())

    async def _send_eteams_register(self) -> None:
        """
        发送 eteams 注册消息
        """
        if not self.eteams_ws:
            return

        # 使用服务器返回的 connId
        conn_id = self.eteams_conn_id or f"{int(time.time() * 1000)}_{random.randint(1000, 9999)}"

        # 构造消息头 - 注意：time 必须是数字，不是字符串
        message = {
            'head': {
                'label': 'conn_register',
                'userId': self.user_info.user_id,
                'eteamsId': self.user_info.eteams_id,
                'time': int(time.time() * 1000),  # 数字类型
                'empId': self.user_info.emp_id,
                'tenantKey': self.user_info.tenant_key or 'all_teams',
                'ua': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.80 Electron/41.0.3 Safari/537.36 weapp-pc/10.1.16/eteams-desktop ',
                'dtu': 'app-pc',
                'connId': conn_id,
                'wicket': '8446212983395336335'  # 固定值
            },
            'body': {
                '': None,  # 空字符串键，值为 null
                'lisenceFlag': None
            }
        }

        print(f"[DEBUG] 发送注册消息: {json.dumps(message, ensure_ascii=False)}")
        await self.eteams_ws.send(json.dumps(message))
        print(f"发送 eteams 注册消息: {message['head']['label']}")

    async def _send_eteams_heartbeat(self) -> None:
        """
        发送 eteams 心跳
        """
        if not self.eteams_ws:
            return

        message = {
            'head': {
                'label': 'heart_beat',
                'userId': self.user_info.user_id,
                'eteamsId': self.user_info.eteams_id,
                'time': int(time.time() * 1000),  # 数字格式
                'empId': self.user_info.emp_id,
                'tenantKey': self.user_info.tenant_key,
                'ua': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.80 Electron/41.0.3 Safari/537.36 weapp-pc/10.1.16/eteams-desktop ',
                'dtu': 'app-pc',
                'connId': self.eteams_conn_id or '',  # 使用服务器返回的 connId
                'wicket': '8446212983395336335'
            },
            'body': {}
        }

        try:
            await self.eteams_ws.send(json.dumps(message))
            print(f"[{time.strftime('%H:%M:%S')}] ✓ 发送 eteams 心跳")
        except Exception as e:
            print(f"发送心跳失败: {e}")

    async def _eteams_message_loop(self) -> None:
        """
        eteams 消息接收循环
        """
        if not self.eteams_ws:
            return

        try:
            async for message in self.eteams_ws:
                try:
                    data = json.loads(message)
                    head = data.get('head', {})
                    label = head.get('label', 'unknown')

                    print(f"[eteams] 收到消息: {label}")

                    if label == 'connSucc':
                        # 提取服务器返回的 connId
                        self.eteams_conn_id = head.get('connId', '')
                        print(f"  连接成功确认，服务器 connId: {self.eteams_conn_id}")
                        # 收到 connSucc 后发送注册消息
                        await self._send_eteams_register()
                    elif label == 'startHeart':
                        print("  ✓ 服务器请求启动心跳")
                        # 启动心跳循环（只启动一次）
                        if not self._heartbeat_task:
                            self._heartbeat_task = asyncio.create_task(
                                self._heartbeat_loop())
                    elif label == 'heartResp':
                        print("  心跳响应")
                    elif label == 'conn_register':
                        # 注册结果
                        if data.get('success'):
                            print("  ✓ 注册成功！")
                        else:
                            print(f"  ✗ 注册失败: {head.get('msg', 'Unknown')}")
                    else:
                        print(
                            f"  消息内容: {json.dumps(data, ensure_ascii=False)[:200]}")

                except json.JSONDecodeError:
                    print(f"[eteams] 非JSON消息: {message[:100]}")

        except websockets.exceptions.ConnectionClosed:
            print("eteams WebSocket 连接已关闭")
        except Exception as e:
            print(f"eteams 消息循环错误: {e}")

    async def _im_message_loop(self):
        if not self.im_ws:
            return

        try:
            async for message in self.im_ws:
                try:
                    data = json.loads(message)
                    header = data.get('header', {})
                    cmd_str = header.get('cmd', 'unknown')
                    try:
                        cmd = int(cmd_str)
                    except ValueError:
                        cmd = cmd_str

                    print(f"[IM] 收到消息: CMD {cmd_str}")

                    # IM 登录成功响应 (CMD 15001)
                    if cmd == 15001:
                        # 检查是否有错误字段
                        if data.get('code') and str(data.get('code')) != '0':
                            print(f"  ✗ IM 登录失败: {data.get('msg', 'Unknown')}")
                        else:
                            print("  ✓ IM 登录成功！")
                            # 登录成功后发送在线状态
                            await self._send_im_online_status()
                    elif cmd == 15000:  # 心跳响应
                        print("  ✓ IM 心跳响应 (CMD 15000)")
                    elif cmd == 15003:  # 其他响应
                        print(f"  [IM] CMD 15003 响应")
                    elif cmd == 15005:  # 服务器心跳请求
                        print("  💓 服务器心跳请求，立即响应...")
                        await self._send_im_heartbeat()
                    elif cmd == 15101:  # 消息推送通知
                        body = data.get('body', {})
                        trans_id = body.get('trans_id', '')
                        msg_id = body.get('msgid', '')
                        from_cid = body.get('from_cid', '')
                        from_uid = body.get('from_uid', '')
                        kind = body.get('kind', '')
                        mkind = body.get('mkind', '')

                        print(f"\n{'='*50}")
                        print(f"  [IM] 📨 收到新消息通知")
                        print(f"{'='*50}")
                        print(f"  消息ID: {msg_id}")
                        print(f"  类型: {kind} ({self._get_kind_name(kind)})")
                        print(f"  发送者: {from_uid} @ {from_cid}")
                        print(f"{'='*50}\n")

                        # 存储 msg_id -> sender 映射
                        if msg_id and from_uid:
                            self._message_senders[msg_id] = from_uid

                        # 发送消息确认
                        if msg_id and trans_id:
                            await self._send_im_ack(trans_id, msg_id)

                        # 请求完整消息内容
                        if msg_id and trans_id and from_cid and from_uid:
                            await self._request_message_content(trans_id, msg_id, from_cid, from_uid)

                    elif cmd == 15107:  # 消息内容响应
                        body = data.get('body', {})
                        datas = body.get('datas', {})
                        ret = body.get('ret', {})

                        print(f"\n{'='*50}")
                        print(f"  [IM] 📬 收到完整消息内容")
                        print(f"{'='*50}")

                        if ret.get('ret') == '0':
                            msg_data = datas.get('msg', {})
                            if isinstance(msg_data, str):
                                try:
                                    msg_data = json.loads(msg_data)
                                except:
                                    msg_data = {}

                            # 解析消息内容
                            msg_type = msg_data.get('type', '')
                            dt_list = msg_data.get('dt', [])

                            ser_msgid = datas.get('ser_msgid', '')
                            # 从映射中获取发送者 ID（如果 datas 中没有）
                            sender_uid = datas.get(
                                'suid') or self._message_senders.get(ser_msgid, '')
                            sender_name = datas.get('sname', '')
                            sender_cid = datas.get('scid', '')

                            print(f"  消息ID: {ser_msgid}")
                            print(f"  消息类型: {msg_type}")
                            print(f"  发送者: {sender_name} ({sender_uid})")

                            # 解析文本内容
                            text_content = ''
                            if dt_list:
                                for item in dt_list:
                                    txt_data = item.get('txt', {})
                                    if txt_data:
                                        text = txt_data.get('v', '')
                                        if text:
                                            print(f"\n  📝 内容:")
                                            print(f"     {text}")
                                            text_content = text

                            # 通知所有注册的回调
                            if self.message_callbacks:
                                callback_data = {
                                    'msg_id': ser_msgid,
                                    'msg_type': msg_type,
                                    'sender_name': sender_name,
                                    'sender_uid': sender_uid,
                                    'sender_cid': sender_cid,
                                    'content': text_content,
                                    'raw_data': {
                                        'datas': datas,
                                        'msg_data': msg_data
                                    }
                                }
                                await self._notify_message(callback_data)

                            # 清理映射
                            if ser_msgid in self._message_senders:
                                del self._message_senders[ser_msgid]
                        else:
                            print(f"  ✗ 获取消息失败: {ret.get('ret')}")

                        print(f"{'='*50}\n")
                    elif cmd == 15509:  # 会话状态更新
                        body = data.get('body', {})
                        print(f"  [IM] 会话状态更新:")
                        print(f"     trans_id: {body.get('trans_id')}")
                        print(f"     flag: {body.get('flag')}")
                        info = body.get('info', {})
                        if info:
                            fuser = info.get('fuser', {})
                            print(
                                f"     会话用户: {fuser.get('uid')} @ {fuser.get('cid')}")
                            print(f"     会话类型: {info.get('session_type')}")
                    elif cmd == 15510:  # 会话列表
                        print(f"  [IM] 收到会话列表")
                    elif cmd == 15511:  # 会话消息列表
                        print(f"  [IM] 收到会话消息列表")
                    elif cmd == 15512:  # 消息已读状态
                        print(f"  [IM] 消息已读状态更新")
                    else:
                        print(
                            f"  [IM] 未处理命令 {cmd}: {json.dumps(data, ensure_ascii=False)[:200]}")

                except json.JSONDecodeError:
                    print(f"[IM] 非JSON消息: {message[:100]}")

        except websockets.exceptions.ConnectionClosed as e:
            print(f"IM WebSocket 连接已关闭: code={e.code}, reason={e.reason}")
            # 尝试重新连接
            if self._running:
                print("尝试重新连接 IM WebSocket...")
                await asyncio.sleep(5)
                # 重新获取 token 并连接
                try:
                    im_token_data = self.get_im_token()
                    token = im_token_data.get('token', '')
                    await self.connect_im_websocket(im_token_data.get('host', ''), token)
                except Exception as reconnect_error:
                    print(f"IM 重新连接失败: {reconnect_error}")
        except Exception as e:
            print(f"IM 消息循环错误: {e}")

    async def _send_im_heartbeat(self) -> None:
        """
        发送 IM 心跳 (CMD 15000)
        """
        if not self.im_ws:
            return

        message = {
            'header': {
                'cmd': 15000,  # 使用 CMD 15000 作为心跳
                'seq': await self._get_im_seq_async(),  # 使用连续序列号
                'dev': str(self.config.device_type),
                'uid': self.user_info.user_id,
                'cid': self.user_info.company_id,
                'ver': '0'
            },
            'body': {}
        }

        try:
            await self.im_ws.send(json.dumps(message))
            print(f"[{time.strftime('%H:%M:%S')}] ✓ 发送 IM 心跳 (CMD 15000)")
        except Exception as e:
            print(f"发送 IM 心跳失败: {e}")

    async def _request_message_content(self, trans_id: str, msg_id: str, from_cid: str, from_uid: str) -> None:
        """
        请求消息内容 (CMD 15107)
        """
        if not self.im_ws:
            return

        message = {
            'header': {
                'cmd': 15107,
                'seq': await self._get_im_seq_async(),  # 使用连续序列号
                'dev': str(self.config.device_type),
                'uid': self.user_info.user_id,
                'cid': self.user_info.company_id,
                'ver': '0'
            },
            'body': {
                'dev': self.config.device_type,
                'from_cid': from_cid,
                'from_uid': from_uid,
                'msgid': msg_id,
                'trans_id': trans_id
            }
        }

        try:
            await self.im_ws.send(json.dumps(message))
            print(f"  [IM] 📤 请求消息内容: msgid={msg_id}")
        except Exception as e:
            print(f"请求消息内容失败: {e}")

    async def _send_im_online_status(self) -> None:
        """
        发送 IM 在线状态 (CMD 15021)
        """
        if not self.im_ws:
            return

        message = {
            'header': {
                'cmd': 15021,
                'seq': await self._get_im_seq_async(),  # 使用连续序列号
                'dev': str(self.config.device_type),
                'uid': self.user_info.user_id,
                'cid': self.user_info.company_id,
                'ver': '0'
            },
            'body': {
                'status': '1'  # 1=在线
            }
        }

        try:
            await self.im_ws.send(json.dumps(message))
            print(f"[{time.strftime('%H:%M:%S')}] ✓ 发送 IM 在线状态")
        except Exception as e:
            print(f"发送 IM 在线状态失败: {e}")

    async def _send_im_ack(self, trans_id: str, msg_id: str) -> None:
        """
        发送 IM 消息确认 (CMD 15102)
        """
        if not self.im_ws:
            return

        message = {
            'header': {
                'cmd': 15102,
                'seq': await self._get_im_seq_async(),  # 使用连续序列号
                'dev': str(self.config.device_type),
                'uid': self.user_info.user_id,
                'cid': self.user_info.company_id,
                'ver': '0'
            },
            'body': {
                'trans_id': trans_id,
                'msgid': msg_id
            }
        }

        try:
            await self.im_ws.send(json.dumps(message))
            print(f"  [IM] 发送消息确认: msgid={msg_id}")
        except Exception as e:
            print(f"发送 IM 消息确认失败: {e}")

    async def _heartbeat_loop(self, interval: int = 10) -> None:
        """
        心跳循环

        Args:
            interval: 心跳间隔（秒）
        """
        heartbeat_count = 0
        while self._running:
            await asyncio.sleep(interval)
            if self._running:
                # 发送 eteams 心跳
                await self._send_eteams_heartbeat()
                # 发送 IM 心跳
                await self._send_im_heartbeat()

                # 每 6 次心跳（约 60 秒）发送一次在线状态
                heartbeat_count += 1
                if heartbeat_count % 6 == 0:
                    await self._send_im_online_status()

    def get_im_token(self) -> Dict[str, Any]:
        """
        获取 IM Token

        Returns:
            IM Token 信息
        """
        if not self.user_info:
            raise Exception("请先登录")

        url = self._get_full_url('/api/em/msg/getToken')

        headers = {
            'Content-Type': 'application/json',
            'eteamsid': self.user_info.eteamsid
        }

        data = {
            'dev': self.config.device_type,
            'serverUrl': self.config.base_url
        }

        response = self.session.post(url, json=data, headers=headers)
        response.raise_for_status()

        result = response.json()
        print("get_im_token \n")
        print(result)

        if result.get('code') != 200:
            raise Exception(
                f"获取 IM Token 失败: {result.get('msg', 'Unknown error')}")
        data = result.get('data')
        uid = data.get('uid')
        cid = data.get('cid')
        tokenStr = data.get('tokenStr')
        host = "ws://"+data.get('host')

        # 更新 user_info 中的 ID（使用 IM 返回的值）
        if uid:
            self.user_info.user_id = uid
        if cid:
            self.user_info.company_id = cid
        # 注意：empId 应该使用 uid，不是 cid
        if uid:
            self.user_info.emp_id = uid

        print(f"uid: {uid}")
        print(f"cid: {cid}")
        print(f"tokenStr: {tokenStr}")
        print(f"[DEBUG] 更新后的 user_id: {self.user_info.user_id}")
        print(f"[DEBUG] 更新后的 emp_id: {self.user_info.emp_id}")
        print(f"[DEBUG] 更新后的 company_id: {self.user_info.company_id}")

        return {"uid": uid, "cid": cid, "token": tokenStr, "host": host}

    async def connect_im_websocket(self, im_server_url: str, im_token: str) -> None:
        """
        连接 IM WebSocket

        Args:
            im_server_url: IM 服务器地址
            im_token: IM 认证令牌
        """
        ws_url = im_server_url.replace(
            'http://', 'ws://').replace('https://', 'wss://')
        ws_url = f"{ws_url}/ws"

        print(f"\n连接 IM WebSocket: {ws_url}")

        self.im_ws = await websockets.connect(ws_url)
        print("IM WebSocket 连接成功！")

        # 启动 IM 消息接收循环
        asyncio.create_task(self._im_message_loop())
        # 发送登录命令
        await self._send_im_login(im_token)

    async def _send_im_login(self, token: str) -> None:
        """
        发送 IM 登录命令 (CMD 15001)
        """
        if not self.im_ws:
            return

        # 生成 UUID 格式的 imei
        imei = str(uuid_lib.uuid4())

        # 秒级时间戳
        trans_id = str(int(time.time()))

        message = {
            'header': {
                'cmd': 15001,
                'seq': await self._get_im_seq_async(),  # 使用连续序列号
                'dev': self.config.device_type,
                'uid': self.user_info.user_id,
                'cid': self.user_info.company_id,
                'ver': 0
            },
            'body': {
                'appkey': 'eteams',
                'token': token,
                'status': 1,
                'dev': self.config.device_type,
                'imei': imei,
                'version': 0,
                'build': 0,
                'cli_version': '10.1.16',  # 使用正确的客户端版本
                'extends': json.dumps({
                    'eteamsId': self.user_info.eteams_id,
                    'v': '10.0.19041',  # Windows 版本
                    'n': 'MS-WSJ',  # 设备名称
                    'm': 'Windows'  # 操作系统
                }),
                'trans_id': trans_id,  # 秒级时间戳
                'sensitive_confirm': '0'
            }
        }
        print(f"[DEBUG] IM 登录消息: {json.dumps(message, ensure_ascii=False)}")
        await self.im_ws.send(json.dumps(message))
        print(f"发送 IM 登录命令: CMD 15001")

    async def start(self, enable_im: bool = True) -> None:
        """
        启动客户端

        Args:
            enable_im: 是否启用 IM 连接
        """
        # 登录
        self.login()
        im_token_data = self.get_im_token()
        print(im_token_data)
        # 连接 eteams WebSocket
        asyncio.create_task(self.connect_eteams_websocket())

        enable_im = True
        # 连接 IM WebSocket
        if enable_im:

            print(f"\n获取 IM Token 成功")
            print(f"  服务器: {im_token_data.get('serverUrl')}")

            # 解析 token（可能需要 Base64 解码）
            token = im_token_data.get('token', '')
            print(f"  Token: {token[:32]}...")

            asyncio.create_task(self.connect_im_websocket(
                im_token_data.get('host', ''),
                token
            ))

        # 设置运行标志
        self._running = True

        print("\n客户端已启动，按 Ctrl+C 退出...")
        print("注意：心跳循环将在收到服务器 startHeart 消息后自动启动")

    async def send_text_message(self, to_uid: str, content: str, to_cid: str = None, msg_type: str = "1002") -> dict:
        """
        发送文本消息

        Args:
            to_uid: 目标用户ID
            content: 消息内容
            to_cid: 目标公司ID（可选，默认使用当前用户的公司ID）
            msg_type: 消息类型 ("1001"=系统消息, "1002"=文本消息, "1003"=图片等)

        Returns:
            dict: 发送结果，包含:
                - success (bool): 是否成功
                - message (str): 结果消息
                - seq (str): 消息序列号
        """
        if not self.im_ws:
            return {
                'success': False,
                'message': 'IM WebSocket 未连接',
                'seq': None
            }

        if not self.user_info:
            return {
                'success': False,
                'message': '用户未登录',
                'seq': None
            }

        # 使用当前用户的公司ID作为默认值
        if to_cid is None:
            to_cid = self.user_info.company_id

        # 生成时间戳和消息ID
        timestamp = int(time.time() * 1000)
        trans_id = str(int(time.time()))
        cli_msgid = f"{timestamp}{random.randint(1000, 9999)}"

        # 获取序列号
        seq = await self._get_im_seq_async()

        # 构造消息内容 (JSON字符串)
        msg_content = {
            "ver": "1.0",
            "dev": self.config.device_type,
            "guid": "0",
            "cnt": "0",
            "idx": "0",
            "sname": "我",  # 发送者名称，可以使用用户信息中的真实名称
            "suid": self.user_info.user_id,
            "scid": self.user_info.company_id,
            "display": "",
            "sysId": "",
            "weaOaId": "",
            "bgc": "",
            "type": "1",
            "dt": [{
                "txt": {
                    "v": "Assistant: "+ content,
                    "next": "0",
                    "ft": "china"
                }
            }]
        }

        # 构造标题内容 (JSON字符串)
        title_content = {
            "sname": "我",
            "suid": self.user_info.user_id,
            "scid": self.user_info.company_id,
            "display": "0",
            "type": "1",
            "dt": [{
                "txt": {
                    "v": content,
                    "next": "0",
                    "ft": "china"
                }
            }],
            "vv": "",
            "des": ""
        }

        # 构造消息数据 (CMD 15100)
        message_data = {
            'header': {
                'cmd': 15100,
                'seq': seq,
                # "dev": 5,
                'dev': self.config.device_type,
                'uid': self.user_info.user_id,
                'cid': self.user_info.company_id,
                'ver': 0
            },
            'body': {
                'dev': self.config.device_type,
                'cli_msgid': cli_msgid,
                'to_cid': to_cid,
                'to_uid': to_uid,
                'kind': msg_type,  # 消息类型: 1001=系统消息, 1002=文本消息
                'mkind': 1,
                'msg': json.dumps(msg_content, ensure_ascii=False),
                'title': json.dumps(title_content, ensure_ascii=False),
                'flag': 1,
                'trans_id': trans_id,
                'sensitive_confirm': '0'
            }
        }

        try:
            print(
                f"[DEBUG] 发送消息数据: {json.dumps(message_data, ensure_ascii=False)}")
            await self.im_ws.send(json.dumps(message_data))
            print(
                f"[{time.strftime('%H:%M:%S')}] ✓ 发送消息: seq={seq}, to={to_uid}@{to_cid}")
            print(f"  内容: {content}")
            return {
                'success': True,
                'message': '消息已发送',
                'seq': seq
            }
        except Exception as e:
            print(f"[ERROR] 发送消息失败: {e}")
            return {
                'success': False,
                'message': f'发送失败: {str(e)}',
                'seq': seq
            }

    async def stop(self) -> None:
        """
        停止客户端
        """
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self.eteams_ws:
            await self.eteams_ws.close()

        if self.im_ws:
            await self.im_ws.close()

        print("客户端已停止")


async def main():
    """主函数示例"""
    # 配置登录信息
    config = LoginConfig(
        base_url='http://www.guangzh.cr',  # 替换为实际服务器地址
        phone='15813878592',  # 替换为实际手机号
        password='your_password',  # 替换为实际密码
        device_type=9  # 9=Windows
    )

    # 创建客户端
    client = EteamsClient(config)

    try:
        # 启动客户端
        await client.start(enable_im=True)

        # 保持运行
        while client._running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n收到退出信号...")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        await client.stop()


if __name__ == '__main__':
    # 运行主函数
    asyncio.run(main())
