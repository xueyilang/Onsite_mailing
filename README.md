# Onsite Mailing Tool

桌面工具，用于从飞书多维表格读取上门服务记录，按条件筛选数据，生成结构化邮件正文，并通过 Microsoft 365 的 `device code` 登录方式发送邮件。

当前项目已经提供：
- 一个可直接分发的 Windows GUI 程序
- 飞书多维表格查询
- 邮件标题自动生成与手动修改
- 收件人 / 抄送预设选项
- 条件筛选
- 可选附件发送
- 固定邮件签名模板

## 项目目标

该工具主要用于欧洲技术外勤 / 售后场景：
- 用户输入 `KWxx` 和 `方向`
- 工具从飞书表格中筛选符合条件的记录
- 自动拼装邮件主题与 HTML 表格正文
- 用户确认后，通过 Microsoft 365 登录发出邮件

## 主要功能

- 从飞书多维表格读取记录
- 筛选条件：
  - `周数 KW = 用户输入`
  - `方向 = 用户输入`
  - `人员不为空`
- `方向` 支持：
  - 手动输入
  - 预设快捷按钮
  - 大小写不敏感匹配
- 支持“是否已上门”选项：
  - `是`：发送完整字段
  - `否`：只发送精简字段
- 邮件标题：
  - 自动根据 `KWxx` 生成默认标题
  - 可在 GUI 中直接修改
  - 最终以 GUI 输入框中的内容为准
- 邮件签名：
  - 固定模板
  - 自动读取当前登录 Microsoft 365 用户姓名
- 支持添加一个或多个附件
- 使用 Microsoft Graph `device code` 登录发送邮件

## 当前 GUI 功能说明

程序名称：
- `OnsiteServiceMailerGUI.exe`

当前 GUI 包含：
- 周数输入框
- 方向输入框
- 方向预设按钮
- 邮件标题输入框
- 收件人输入框
- 抄送输入框
- 预设收件人 / 抄送勾选项
- 是否已上门单选项
- 查询记录按钮
- 确认并发邮件按钮
- 附件选择与清空
- 查询结果预览

## 邮件内容逻辑

### 标题

默认标题格式：

```text
202x KWxx欧洲技术外勤及售后备品使用情况 KWxx Onsite Service
```

说明：
- `KWxx` 来自用户输入
- 年份优先从筛选结果里的 `日期` 字段推断
- 如果无法从记录中推断，回退到当前德国时间年份
- 用户可以在 GUI 中直接修改标题

### 正文

正文包含：
- 固定中英双语说明
- 自动汇总去重后的 `人员` 名单
- 记录表格
- 固定签名模板

### 签名

当前签名模板包含：
- 德英双语固定内容
- 当前登录用户姓名
- `European Business Unit (BUEU)`
- 公司信息与免责声明

## 飞书数据来源

当前内嵌使用的飞书表：

- `FEISHU_APP_TOKEN = G2GHbHVWRarPAPstB0hjPliRpvf`
- `FEISHU_TABLE_ID = tblHCxh8GzFQMxtO`

已验证可读取该表的字段定义和记录。

## 当前内嵌配置

为了便于同事直接使用，GUI 版本已经将当前必要配置直接内嵌到程序中，不依赖外部 `.env` 才能运行：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_BASE_URL`
- `FEISHU_APP_TOKEN`
- `FEISHU_TABLE_ID`
- `GRAPH_TENANT_ID`
- `GRAPH_CLIENT_ID`

说明：
- 这让 `.exe` 更易分发
- 也意味着敏感配置已打入程序内部
- 如果后续需要更高安全性，建议改成外置配置或后端服务

## 运行方式

### 方式 1：直接运行打包后的 exe

最终程序位于：

```text
dist/OnsiteServiceMailerGUI.exe
```

直接双击运行即可。

### 方式 2：用 Python 运行源码

```powershell
python .\onsite_service_mailer_gui.py
```

## 最简使用说明

1. 打开 `OnsiteServiceMailerGUI.exe`
2. 输入周数，例如 `KW12`
3. 输入方向，或点击下方方向快捷按钮
4. 检查邮件标题、收件人、抄送、是否已上门
5. 如有需要，选择附件
6. 点击 `查询记录`
7. 确认命中记录数正确
8. 点击 `确认并发邮件`
9. 按提示复制 `device code` 并完成 Microsoft 365 登录
10. 登录完成后邮件自动发送

## 收件人 / 抄送逻辑

GUI 允许：
- 手动输入收件人
- 手动输入抄送
- 使用预设勾选项自动补充地址

默认勾选的预设项包括：
- 收件人：
  - `technik.service@alpha-ess.de`
- 抄送：
  - `tech.logistik@alpha-ess.de`
  - `ming.zhou@alpha-ess.com`
  - `service@alpha-ess.de`

## 附件功能

GUI 支持：
- 选择一个或多个附件
- 清空已选附件
- 发送邮件时将附件一并发出

当前最适合的附件类型是：
- PDF

对于当前实际使用场景：
- 10 个 PDF
- 每个约 500 KB

这种体量通常可以正常通过 Microsoft Graph `sendMail` 发出。

## Microsoft 365 登录方式

发送邮件使用：
- Microsoft Graph
- `device code` 登录

流程：
- 程序弹出大号 `device code` 窗口
- 用户点击“复制代码并打开网页”
- 浏览器打开 Microsoft 登录页
- 登录完成后程序自动继续发送

## 字段处理逻辑

### 方向

方向字段当前支持的快捷选项：
- Berlin
- München
- NRW
- One Day
- Dresden
- Stuttgurt
- Würzburg
- Hamburg
- Bremen
- Nürnberg
- Trier
- Oldenburg
- Leipzig
- NRW+Hannover
- Österreich
- Switzerland

### 人员汇总

用于正文说明中的 `人员` 名单会：
- 自动拆分逗号
- 自动兼容中文逗号
- 自动去重

## 代码结构

主要文件：

- `onsite_service_mailer_gui.py`
  - 主 GUI 程序
- `app.py`
  - 早期飞书导出 + 邮件脚本
- `send_test_mail.py`
  - 最小邮件测试脚本
- `send_kw12_onsite_service_mail.py`
  - 早期单用途测试脚本
- `pyinstaller_hooks/hook-tkinter.py`
  - 自定义 PyInstaller hook
- `OnsiteServiceMailerGUI.spec`
  - 打包配置

## 打包方式

当前使用 `PyInstaller` 打包：

```powershell
$env:TCL_LIBRARY='C:\Users\Marco Xue\AppData\Local\Programs\Python\Python312\tcl\tcl8.6'
$env:TK_LIBRARY='C:\Users\Marco Xue\AppData\Local\Programs\Python\Python312\tcl\tk8.6'
python -m PyInstaller --noconsole --onefile --clean --name OnsiteServiceMailerGUI --additional-hooks-dir .\pyinstaller_hooks --hidden-import tkinter --hidden-import tkinter.ttk --hidden-import tkinter.messagebox --hidden-import _tkinter --add-data "C:\Users\Marco Xue\AppData\Local\Programs\Python\Python312\tcl\tcl8.6;tcl\tcl8.6" --add-data "C:\Users\Marco Xue\AppData\Local\Programs\Python\Python312\tcl\tk8.6;tcl\tk8.6" onsite_service_mailer_gui.py
```

说明：
- 这里显式带入了 `tcl/tk` 资源
- 同时使用自定义 `hook-tkinter.py`
- 这是为了避免打包后出现 `No module named 'tkinter'`

## 已知注意事项

### 1. Windows 安全策略 / Smart App Control

同事电脑上运行 `.exe` 时，可能会因为：
- Smart App Control
- SmartScreen
- 企业安全策略

而被拦截。

这不是程序逻辑错误，而是未签名内部程序常见现象。

### 2. Outlook 默认签名

当前程序不会自动读取 Outlook 默认签名模板。  
原因是 Microsoft Graph 不提供可靠的 API 来读取 Outlook 默认邮件签名。

因此目前使用的是：
- 程序内固定签名模板

### 3. 触摸板签字 / 电子签名

当前项目聚焦于：
- 飞书取数
- 自动发邮件

尚未实现：
- 电子上门单生成
- 现场签字
- PDF 回签归档

## 后续可扩展方向

- 电子上门单模板生成
- PDF/Word 自动预填
- 客户现场签字
- 已签 PDF 回写飞书
- 飞书应用 / 插件入口
- 更完善的签名模板 UI
- 多语言模板切换

## 仓库说明

本项目已推送到：

```text
https://github.com/xueyilang/Onsite_mailing.git
```

## 免责提示

由于当前版本已将部分连接配置内嵌到程序中：
- 适合内部可信团队使用
- 不建议直接面向不受控环境广泛分发

如需长期正式使用，建议后续升级为：
- 外置配置
- 或后端服务化方案
