#!/usr/bin/env python3
"""使用 Playwright 抓取 X(Twitter) 指定用户时间线推文。

注意：
1. 请遵守当地法律法规以及 X 平台条款。
2. 页面结构经常变化，选择器可能需要维护。
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


@dataclass
class Tweet:
    tweet_id: str
    author_handle: str
    url: str
    text: str
    created_at: str
    scraped_at: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="抓取指定 X(Twitter) 用户推文并保存为 JSONL/CSV"
    )
    parser.add_argument("username", help="目标用户名（不带 @）")
    parser.add_argument("-n", "--max-tweets", type=int, default=30, help="最多抓取推文数量")
    parser.add_argument(
        "-o",
        "--output",
        default="tweets.jsonl",
        help="输出文件路径（默认 tweets.jsonl）",
    )
    parser.add_argument(
        "--format",
        choices=["jsonl", "csv"],
        default="jsonl",
        help="输出格式（默认 jsonl）",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="使用无头模式运行浏览器（默认有头，便于手动登录）",
    )
    parser.add_argument(
        "--user-data-dir",
        default=".twitter_profile",
        help="Playwright 持久化用户目录，用于保存登录态",
    )
    parser.add_argument(
        "--manual-login",
        action="store_true",
        help="启动后先打开 x.com 并等待手动登录，按回车继续抓取",
    )
    parser.add_argument(
        "--max-scrolls",
        type=int,
        default=80,
        help="最多滚动次数，防止无限滚动",
    )
    parser.add_argument(
        "--scroll-wait",
        type=float,
        default=1.3,
        help="每次滚动后的等待秒数",
    )
    return parser.parse_args()


def extract_tweets(page) -> List[Tweet]:
    raw_items = page.eval_on_selector_all(
        "article[data-testid='tweet']",
        """
        (nodes) => nodes.map(node => {
          const statusLink = node.querySelector("a[href*='/status/']");
          const href = statusLink ? statusLink.getAttribute('href') : '';
          const idMatch = href ? href.match(/\/status\/(\d+)/) : null;
          const tweetId = idMatch ? idMatch[1] : '';

          const text = node.querySelector("div[data-testid='tweetText']")?.innerText || '';
          const timeNode = node.querySelector('time');
          const createdAt = timeNode ? timeNode.getAttribute('datetime') : '';

          const authorMatch = href ? href.match(/^\/(.+?)\/status\//) : null;
          const authorHandle = authorMatch ? authorMatch[1] : '';

          return {
            tweet_id: tweetId,
            author_handle: authorHandle,
            url: href ? `https://x.com${href}` : '',
            text,
            created_at: createdAt,
          };
        });
        """,
    )

    scraped_at = datetime.now(timezone.utc).isoformat()
    tweets: List[Tweet] = []
    for item in raw_items:
        if not item.get("tweet_id"):
            continue
        tweets.append(
            Tweet(
                tweet_id=item["tweet_id"],
                author_handle=item.get("author_handle", ""),
                url=item.get("url", ""),
                text=item.get("text", "").strip(),
                created_at=item.get("created_at", ""),
                scraped_at=scraped_at,
            )
        )
    return tweets


def save_jsonl(output: Path, tweets: List[Tweet]) -> None:
    with output.open("w", encoding="utf-8") as f:
        for tweet in tweets:
            f.write(json.dumps(asdict(tweet), ensure_ascii=False) + "\n")


def save_csv(output: Path, tweets: List[Tweet]) -> None:
    fields = ["tweet_id", "author_handle", "url", "text", "created_at", "scraped_at"]
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for tweet in tweets:
            writer.writerow(asdict(tweet))


def scrape(username: str, max_tweets: int, headless: bool, user_data_dir: str, manual_login: bool, max_scrolls: int, scroll_wait: float) -> List[Tweet]:
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            viewport={"width": 1280, "height": 1800},
        )
        page = context.new_page()

        if manual_login:
            page.goto("https://x.com", wait_until="domcontentloaded")
            print("请在打开的浏览器中完成登录，然后回到终端按回车继续...")
            input()

        target_url = f"https://x.com/{username.lstrip('@')}"
        print(f"打开目标主页: {target_url}")
        page.goto(target_url, wait_until="domcontentloaded")

        try:
            page.wait_for_selector("article[data-testid='tweet']", timeout=15000)
        except PlaywrightTimeoutError:
            print("警告：未在预期时间内加载到推文，可能需要先登录或该用户不可见。")

        seen: Dict[str, Tweet] = {}
        stalled_rounds = 0

        for i in range(max_scrolls):
            current = extract_tweets(page)
            before = len(seen)
            for t in current:
                seen.setdefault(t.tweet_id, t)

            after = len(seen)
            print(f"滚动 {i + 1}/{max_scrolls}，累计推文: {after}")

            if after >= max_tweets:
                break

            if after == before:
                stalled_rounds += 1
            else:
                stalled_rounds = 0

            if stalled_rounds >= 5:
                print("连续多次无新增推文，停止滚动。")
                break

            page.mouse.wheel(0, 4000)
            time.sleep(scroll_wait)

        context.close()

    tweets = sorted(seen.values(), key=lambda x: x.created_at or "", reverse=True)
    return tweets[:max_tweets]


def main() -> None:
    args = parse_args()
    tweets = scrape(
        username=args.username,
        max_tweets=args.max_tweets,
        headless=args.headless,
        user_data_dir=args.user_data_dir,
        manual_login=args.manual_login,
        max_scrolls=args.max_scrolls,
        scroll_wait=args.scroll_wait,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "jsonl":
        save_jsonl(output, tweets)
    else:
        save_csv(output, tweets)

    print(f"完成：已保存 {len(tweets)} 条推文到 {output}")


if __name__ == "__main__":
    main()
