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

> 想让 AI agent 帮你部署？让它执行下面几行即可：
>
> ```bash
> git clone https://github.com/<你的用户名>/xuanke-assistant.git
> cd xuanke-assistant
> pip install -r requirements.txt
> python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
> ```
>
> 然后打开 http://localhost:8000（课程数据已随仓库内置，无需导入）。

想给同宿舍/同班同学用？同一 WiFi 下访问 `http://你的IP:8000`（服务用 `--host 0.0.0.0` 启动，已支持）；不在同一网络可用 `cloudflared tunnel --url http://localhost:8000` 生成临时公网地址。**每人本地运行、Key 只存在各自电脑上** 是推荐姿势。

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
