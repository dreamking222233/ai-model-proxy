# Impl: 登录页忘记密码找回

**日期**: 2026-04-27
**功能**: `forgot-password`
**状态**: 已完成实现与验证

## 一、任务概述

本次在平台登录页 `/login` 新增“忘记密码”找回能力，用户可以通过“账号 + 邮箱”校验身份后，直接设置新密码覆盖旧密码。

实现范围：

1. 平台登录页新增“忘记密码？”入口
2. 点击后弹出找回密码表单
3. 用户输入账号、邮箱、新密码、确认新密码后提交
4. 后端校验账号与邮箱匹配关系，校验通过后更新密码哈希
5. 代理登录页 `/agents/login` 不展示该入口

## 二、文件变更清单

- `backend/app/schemas/user.py`
- `backend/app/api/auth.py`
- `backend/app/services/auth_service.py`
- `backend/app/test/test_auth_service.py`
- `frontend/src/api/auth.js`
- `frontend/src/views/Login.vue`
- `md/plan-forgot-password-20260427.md`

## 三、核心实现说明

### 3.1 后端接口

文件：

- `backend/app/api/auth.py`
- `backend/app/schemas/user.py`
- `backend/app/services/auth_service.py`

新增接口：

- `POST /api/auth/forgot-password`

请求体字段：

- `username`
- `email`
- `new_password`

处理逻辑：

1. 对用户名做 `trim`
2. 对邮箱做 `trim + lower`
3. 根据当前访问站点补充账号范围限制：
   - 平台站点仅允许找回 `agent_id = NULL` 的平台账号
   - 代理站点仅允许找回当前代理下的账号
   - 本地开发域名保留原有宽松行为
4. 使用用户名与邮箱联合匹配用户
5. 不匹配时返回 `账号或邮箱不匹配`
6. 账号禁用时返回 `账号已被禁用`
7. 通过 `hash_password(...)` 重新生成密码哈希并覆盖旧值

本次没有新增数据库字段，也没有引入邮件发送、验证码或重置 token 表。

### 3.2 前端交互

文件：

- `frontend/src/api/auth.js`
- `frontend/src/views/Login.vue`

前端调整：

1. 新增 `forgotPassword(...)` API 封装
2. 在登录表单按钮下方新增“忘记密码？”入口
3. 点击后打开暗色风格弹窗
4. 弹窗内提供账号、邮箱、新密码、确认新密码字段
5. 前端校验两次密码一致
6. 重置成功后自动关闭弹窗，并把用户名回填到登录表单

### 3.3 测试覆盖

文件：

- `backend/app/test/test_auth_service.py`

新增 4 个单测：

1. 用户名与邮箱匹配时可以更新密码哈希
2. 账号与邮箱不匹配时拒绝重置
3. 已禁用账号拒绝重置
4. 代理站点会把账号查找范围限制在当前代理内

## 四、测试验证

已执行：

```bash
python -m py_compile backend/app/schemas/user.py backend/app/api/auth.py backend/app/services/auth_service.py backend/app/test/test_auth_service.py
```

结果：通过。

已执行：

```bash
env PYTHONPATH=backend python -m unittest backend.app.test.test_auth_service
```

结果：

- `Ran 4 tests`
- `OK`

说明：

- 运行时出现 `passlib/bcrypt` 版本信息告警，但不影响本次测试通过

已执行：

```bash
npm run build
```

结果：

- 前端构建成功
- 存在项目原有 bundle 体积告警，不影响本次功能

## 五、使用方式

1. 打开 `/login`
2. 点击“忘记密码？”
3. 输入账号、注册邮箱、新密码、确认新密码
4. 提交成功后，使用新密码重新登录
