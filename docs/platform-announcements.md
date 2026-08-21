# 平台公告管理

## 功能范围

管理端 `/admin/announcements` 用于维护公告：

- 直营固定开屏公告：只影响平台直营用户登录后的第一条开屏公告。
- 额外公告：管理端发布后面向全部用户展示，包括直营用户和代理站点用户。

## 用户端展示规则

用户端通过 `GET /api/user/profile/announcements` 获取当前公告列表：

1. 直营用户先返回管理端配置的直营固定开屏公告。
2. 代理站点用户先返回代理端在 `/agent/system` 配置的固定开屏公告。
3. 再追加管理端已发布的额外公告。

Dashboard 登录后会按顺序弹出设置为开屏展示的公告，并使用 `sessionStorage` 记录当前会话已弹出状态。Header 头像左侧公告图标可随时打开公告抽屉查看当前公告。

## 数据结构

额外公告存储于 `platform_announcement`：

- `title`：公告标题。
- `content`：公告内容。
- `status`：`draft`、`published`、`offline`。
- `show_popup`：是否登录开屏弹出。
- `sort_order`：排序值，越大越靠前。
- `published_at`：发布时间。

直营固定开屏公告沿用 `system_config`：

- `platform_announcement_title`
- `platform_announcement_content`
- `platform_support_wechat`
- `platform_support_qq`
