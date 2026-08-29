# 🎓 选课助手

一个**本机运行、数据不出门**的选课工作台：课程数据已内置，下载即用——AI 对话查课、手动多条件筛选、避开没空时段、收藏备选课。

- **左侧对话**：用大白话提需求（"周三下午没空，想找 2 学分的公选课"），AI 自动查库并把结果推成表格
- **手动查课**：点「新建查询卡」，按课程名称 / 课程号 / 课程类别 / 课程归属组合筛选，可只看有余量、避开已占时段
- **右侧表格区**：多张表格以标签页并存；列头筛选（课程号、余量等全量升序列出、支持搜索）、本表快搜、列设置、按余量/时段冲突实时重查
- **已占时段标记**：把你没空的时间点上色（支持按周次细分），查询和 AI 默认避开
- **收藏备选课**：勾选课程行即可收藏，左侧「我的收藏」随时查看，已收藏的行浅黄高亮
- **隐私**：API Key 只存本机（`config.local.json`，不进 git）

> 数据口径：余量 = 教学班人数 − 选课人数（导出时刻快照），负数表示超选、如实显示。**AI 生成回复仅供参考。**

## 快速开始（3 步）

1. 安装 [Python 3.10+](https://www.python.org/downloads/)（勾选 *Add Python to PATH*）
2. 下载本项目（页面绿色 **Code → Download ZIP**，或 `git clone`），解压后**双击 `启动.bat`**——首次会自动创建虚拟环境、安装依赖（约 2 分钟，已配国内镜像加速），完成后浏览器自动打开
3. 左侧「**AI 设置**」填入 API Key 即可开始对话（接口地址与模型已预填，一般只需填 Key；不配置也不影响手动查课）。没有 Key？向作者索取，或在智谱开放平台 open.bigmodel.cn 注册，`glm-4-flash` 模型免费

想给同宿舍/同班同学用？同一 WiFi 下访问 `http://你的IP:8000`（服务用 `--host 0.0.0.0` 启动，已支持）；不在同一网络可用 `cloudflared tunnel --url http://localhost:8000` 生成临时公网地址。**每人本地运行、Key 只存在各自电脑上** 是推荐姿势。

## 让 AI Agent 帮你部署

懒得动手？把下面这段话完整复制给任意 AI agent（Claude Code、Cursor 等），它会自动完成下载、装环境、启动：

```text
请帮我在本机部署一个开源工具「选课助手」（选课查询工作台），按以下步骤执行：

1. 环境检查：确认本机有 Python 3.10+（运行 python --version）。如果没有，
   提示我去 python.org 安装并勾选 "Add Python to PATH"，等我装好后继续。

2. 获取代码：先问我希望把工具安装到哪个目录（可以给我推荐，如 Windows 的
   D:\xuanke-assistant 或桌面），确认后在那个位置
   git clone https://github.com/newnewself/xuanke-assistant.git
   并进入 xuanke-assistant 目录。（没有 git 就从仓库页面下载 ZIP 解压到该位置）

3. 安装依赖（在项目目录下）：
   python -m venv .venv
   激活虚拟环境：Windows 用 .venv\Scripts\activate，macOS/Linux 用 source .venv/bin/activate
   pip install -r requirements.txt
   （下载慢就加国内镜像：-i https://pypi.tuna.tsinghua.edu.cn/simple）

4. 启动服务：python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   然后确认 http://localhost:8000 可以正常打开。
   课程数据已内置在 data/courses.db，无需任何导入步骤。

5. 启动成功后提醒我最后一步：在网页左侧「AI 设置」填入 API Key 才能使用
   AI 对话（Key 我自己向工具作者索取，或在智谱开放平台 open.bigmodel.cn
   注册免费领取 glm-4-flash 的 Key）。不填 Key 也能正常手动查课。

注意事项：
- 不要构建前端，frontend/dist 已预构建，直接用
- 不要修改/删除 data/ 目录里的课程数据文件
- 如果 8000 端口被占用，换一个端口启动并把新地址告诉我
- 部署完成后明确告诉我两件事：工具安装在哪个目录；以后如何再次启动
  （进入安装目录双击 启动.bat 即可，或运行第 4 步的启动命令）
- 任何一步报错，把完整错误信息给我看再继续
```

极简版（agent 会自行阅读本 README 完成部署）：

```text
帮我把 https://github.com/newnewself/xuanke-assistant 克隆到本机并运行起来，
仓库 README 里有完整的部署步骤，照着做，完成后告诉我怎么用。
```

## 手动运行（开发者）

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000   # 前端已预构建到 frontend/dist，随仓库分发

# 前端开发（需要 Node 18+）
cd frontend && npm install && npm run dev     # http://localhost:5173，/api 自动代理到 8000
npm run build                                 # 产物输出 frontend/dist

# 测试
python -m pytest tests/ -q
```

命令行重建课程数据库：`python -m app.etl "按条件查询课程.xlsx"`

## 项目结构

```
选课助手/
├── app/
│   ├── etl.py          # Excel → 清洗聚合（按选课课号）→ SQLite，时间文本解析为结构化时段
│   ├── engine.py       # 纯逻辑：星期×节次×周次(+单双周) 解析与冲突计算、查询精筛
│   ├── agent.py        # LLM Agent：3 个工具(search/detail/present_table) + SSE 事件流
│   └── routers/        # courses / chat / settings / admin / source 五组 API
├── frontend/           # React 18 + TypeScript + Ant Design（Vite），dist 预构建随仓库分发
├── tests/              # 时间解析/冲突/搜索/分类的单元测试（30 项）
├── data/               # courses.db + 课程表格文件（随仓库分发，开箱即用）
├── sample/             # 课程表样例（脱敏）
└── 启动.bat
```

## 设计原则

**LLM 不接触原始数据表，只调用工具。** 冲突判定、余量计算全部由确定性代码完成，AI 的每条课程信息都来自工具返回、服务端校验选课课号——查出来的结果是算出来的，不是模型编的。数据量 4000 班级量级，SQLite 单文件零部署。

## 路线图

- [x] v1：AI 对话查课 / 手动查询卡 / 已占时段 / 收藏备选课 / 结果表格工作台
- [ ] 课程间两两冲突检测（星期×节次×周次求交已实现，待接入 UI）
- [ ] 自动拼课表（固定课打底 + 目标学分，回溯出前 N 个方案）
- [ ] 周课表网格可视化、课表导出（Excel/ics）

## License

MIT
