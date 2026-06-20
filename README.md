# Dify Langfuse Dataset Evaluator

用于批量评测 Dify Chat App 的实际响应是否符合 Langfuse Dataset 中的预期结果。

项目会读取 Langfuse Dataset item，把每条用例发送到 Dify `/chat-messages` 接口，再把评测分数写回 Langfuse Dataset Run。适合做 Dify 应用的回归测试、UAT 验收、提示词或知识库变更后的自动化对比。

## 功能

- 从 Langfuse Dataset 拉取评测用例，并创建一次 Dataset Run。
- 调用 Dify Chat App，支持 `streaming` 和阻塞响应模式。
- 支持 Dataset item 覆盖 Dify `query`、`inputs`、`conversation_id` 和 `files`。
- 支持固定答案包含判断、文本相似度判断、关键词全量命中判断。
- 每条用例写入两个分数：
  - `answer_similarity`：答案相似度或关键词命中比例。
  - `passed`：是否达到阈值，达标为 `1.0`，否则为 `0.0`。
- 支持限制运行条数和并发数，便于先小批量验证。

## 目录结构

```text
.
├── .env.example
├── pyproject.toml
├── README.md
├── src/
│   └── dify_langfuse_validator/
│       ├── cli.py
│       ├── config.py
│       ├── dify_client.py
│       ├── evaluator.py
│       └── langfuse_runner.py
└── tests/
    ├── test_evaluator.py
    └── test_langfuse_runner.py
```

当前采用标准 `src/` layout，业务包是 `dify_langfuse_validator`。`tests/__pycache__/`、`.idea/` 等本地运行或 IDE 产物不需要提交。

## 安装

在仓库根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

如果安装时报错 `Missing dependencies for SOCKS support`，说明当前 shell 配了 `socks5://` 代理，但 pip 没有 SOCKS 支持。可以先把代理改成 HTTP 形式再安装：

```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
unset all_proxy

python3 -m pip install -U pip setuptools wheel
python3 -m pip install -e ".[dev]"
```

如果你的代理只支持 SOCKS，则先安装 SOCKS 支持：

```bash
python3 -m pip install "pip[socks]"
python3 -m pip install -e ".[dev]"
```

## 配置

编辑 `.env`：

```env
LANGFUSE_SECRET_KEY="sk-xxx"
LANGFUSE_PUBLIC_KEY="pk-xxx"
LANGFUSE_BASE_URL="http://langfuse.example.com"

DIFY_BASE_URL="https://api.dify.ai/v1"
DIFY_API_KEY="app-xxx"
DIFY_USER="eval-user"

DIFY_DEFAULT_INPUTS='{"x_dify_chat_id":"xxx","x_menu_id":"xxx"}'
DIFY_DEFAULT_CONVERSATION_ID=""
DIFY_RESPONSE_MODE="streaming"
REQUEST_TIMEOUT_SECONDS=120
```

说明：

- `.env` 默认从仓库根目录读取。
- `DIFY_DEFAULT_INPUTS` 必须是 JSON object 字符串。
- Dataset item 中的 `inputs` 会覆盖或追加到 `DIFY_DEFAULT_INPUTS`。
- Dataset item metadata 中的 `conversation_id`、`files` 会覆盖默认请求上下文。

## 使用

运行完整 Dataset：

```bash
dify-langfuse-validate run --dataset "your-dataset-name"
```

指定 run 名称、通过阈值、运行条数和并发数：

```bash
dify-langfuse-validate run \
  --dataset "your-dataset-name" \
  --run-name "uat-001" \
  --threshold 0.8 \
  --limit 10 \
  --max-concurrency 3
```

参数：

- `--dataset, -d`：Langfuse Dataset 名称，必填。
- `--run-name, -r`：Langfuse Dataset Run 名称；不传时自动生成。
- `--threshold, -t`：通过阈值，默认 `0.8`。
- `--limit, -l`：只运行前 N 条 Dataset item。
- `--max-concurrency, -c`：并发调用 Dify 的最大数量，默认 `3`。

## Dataset Item 格式

最简单的格式：

```json
{
  "input": "订单状态怎么查？",
  "expected_output": "可以帮你查询订单状态"
}
```

带 Dify 业务上下文：

```json
{
  "input": {
    "query": "查询订单 12345",
    "inputs": {
      "x_dify_chat_id": "b68d5d53-dcad-4837-9e06-c0075addba36",
      "x_menu_id": "157446200875562803"
    }
  },
  "expected_output": "订单 12345",
  "metadata": {
    "conversation_id": "17c72647-a786-44d7-bb54-32f7c9fb282b"
  }
}
```

关键词评测：

```json
{
  "input": {
    "question": "你能做什么"
  },
  "expected_output": {
    "expected_keywords": ["查询", "订单"]
  }
}
```

`expected_keywords` 可以是字符串，也可以是数组。数组模式下必须全部命中才算通过；缺失部分关键词时，`answer_similarity` 会按命中比例给分。

## 评测规则

1. 如果预期文本被 Dify 回答完整包含，`answer_similarity = 1.0`。
2. 如果使用 `expected_keywords`：
   - 字符串：按普通包含判断。
   - 数组：每个关键词都必须出现在回答中。
3. 如果不满足包含判断，则对普通预期文本使用 `difflib.SequenceMatcher` 计算相似度。
4. `passed` 根据 `answer_similarity >= --threshold` 计算。

## 测试

```bash
pytest -q
```

或：

```bash
python3 -m pytest -q
```
