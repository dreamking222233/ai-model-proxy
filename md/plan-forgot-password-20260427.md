# Plan: 登录页忘记密码找回

**日期**: 2026-04-27
**功能**: `forgot-password`
**任务规模**: 中型

## 一、用户原始需求

阅读当前目录下的项目及相关代码进行分析。当前在 `/login` 页面添加一个忘记密码并找回的功能，点击后可以通过输入账号和邮箱进行找回，然后重新输入最新的密码，覆盖旧密码。

## 二、技术方案

### 后端

- 在 `backend/app/schemas/user.py` 新增忘记密码请求体，包含：
  - `username`
  - `email`
  - `new_password`
- 在 `backend/app/services/auth_service.py` 新增 `reset_password_by_identity(...)`
- 重置逻辑采用“用户名 + 邮箱”双字段校验，不新增邮件发送、验证码和 token 表
- 校验项：
  - 用户存在
  - 用户名与邮箱匹配
  - 账号未被禁用
  - 新密码长度符合现有规则
- 校验通过后直接覆盖 `password_hash`
- 在 `backend/app/api/auth.py` 暴露 `POST /api/auth/forgot-password`
- 错误提示保持中文，继续沿用 `ServiceException`

### 前端

- 在 `frontend/src/api/auth.js` 新增忘记密码接口调用
- 在 `frontend/src/views/Login.vue` 的登录模式下新增“忘记密码”入口
- 点击后在当前页打开找回密码表单，不新建独立路由，避免打断现有登录/注册切换
- 表单字段：
  - 用户名
  - 邮箱
  - 新密码
  - 确认新密码
- 提交成功后提示用户密码已重置，并切回登录表单
- 代理登录页 `/agents/login` 不展示该入口，避免和代理后台账号管理逻辑混淆

### 验证

- 补充后端单测，覆盖：
  - 用户名与邮箱匹配时可重置密码
  - 邮箱不匹配时拒绝重置
  - 已禁用账号拒绝重置
- 执行 Python 编译检查
- 执行前端构建验证

## 三、涉及文件

- `backend/app/schemas/user.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/auth.py`
- `backend/app/test/test_auth_service.py`
- `frontend/src/api/auth.js`
- `frontend/src/views/Login.vue`
- `md/impl-forgot-password-20260427.md`

## 四、实施步骤

1. 新增后端忘记密码 schema 和接口
2. 实现账号 + 邮箱校验后的密码重置服务
3. 补充后端单测覆盖成功与失败分支
4. 扩展前端认证 API 封装
5. 调整登录页，加入忘记密码入口与找回表单
6. 联调成功提示、异常提示与表单切换逻辑
7. 执行后端测试、Python 编译和前端构建
8. 补充 `impl` 文档并执行一次自审
