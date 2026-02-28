# Twitter/X 用户推文抓取脚本

这是一个基于 **Playwright** 的浏览器自动化脚本，用来抓取指定用户公开时间线中的推文，并导出为 `JSONL` 或 `CSV`。

## 1. 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install playwright
python -m playwright install chromium
```

## 2. 使用方法

### 首次建议手动登录（保存登录态）

```bash
python twitter_scraper.py elonmusk --manual-login -n 50 -o data/elonmusk.jsonl --format jsonl
```

执行后会先打开 `x.com`，你可以在浏览器中登录。登录成功后回终端按回车，脚本会进入目标主页抓取推文。

### 后续直接抓取

```bash
python twitter_scraper.py elonmusk -n 100 -o data/elonmusk.csv --format csv --headless
```

## 3. 参数说明

- `username`：目标用户名（不带 `@`）。
- `-n, --max-tweets`：最多抓取条数，默认 `30`。
- `-o, --output`：输出文件路径。
- `--format`：`jsonl` 或 `csv`。
- `--headless`：无头模式。
- `--user-data-dir`：浏览器登录态保存目录（默认 `.twitter_profile`）。
- `--manual-login`：先手动登录后再抓取。
- `--max-scrolls`：最大滚动次数。
- `--scroll-wait`：每次滚动后等待秒数。

## 4. 注意事项

- X/Twitter 页面结构会变化，选择器可能失效，需要按需维护。
- 平台可能对未登录或高频访问做限制。
- 请务必遵守平台服务条款和当地法律法规。
