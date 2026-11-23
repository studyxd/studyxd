from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from writing_dashboard.articles import inspect_article, scan_articles
from writing_dashboard.covers import candidate_urls
from writing_dashboard.collect import collect_accounts
from writing_dashboard.frontmatter import render_note, split_note
from writing_dashboard.paths import vault_root
from writing_dashboard.pngutil import write_png
from writing_dashboard.rss import parse_feed
from writing_dashboard.scaffold import create_article, create_social
from writing_dashboard.social import inspect_social
from writing_dashboard.sync import sync_vault

ROOT = vault_root()
SENTINEL = "THIS_FULL_ARTICLE_SENTENCE_SHOULD_NOT_BE_STORED"


class FrontmatterTests(unittest.TestCase):
    def test_roundtrip_keeps_dates_bare_and_quotes_text(self):
        note = render_note(
            {
                "title": "标题：有冒号",
                "published": "2026-11-21T00:54:00",
                "day": "2026-11-21",
                "date": "2026-11-21",
                "cover": "[[topic-radar/wechat-covers/a.jpg]]",
                "reads": 12,
                "status": "可借鉴",
            },
            "批注留在正文",
            ["title", "published", "day", "date", "cover", "reads", "status"],
        )
        self.assertIn("\npublished: 2026-11-21T00:54:00\n", note)
        self.assertIn("\nday: 2026-11-21\n", note)
        self.assertIn("\ndate: 2026-11-21\n", note)
        self.assertNotIn('published: "', note)
        data, body = split_note(note)
        self.assertEqual(data["title"], "标题：有冒号")
        self.assertEqual(data["cover"], "[[topic-radar/wechat-covers/a.jpg]]")
        self.assertEqual(data["status"], "可借鉴")
        self.assertEqual(data["reads"], 12)
        self.assertIn("批注留在正文", body)


class CoverTests(unittest.TestCase):
    def test_proxy_url_unwraps_to_the_original_image(self):
        url = "https://wechat2rss.xlab.app/img-proxy/?k=abc&u=https%3A%2F%2Fmmbiz.qpic.cn%2Fa.jpg"
        self.assertEqual(candidate_urls(url)[0], "https://mmbiz.qpic.cn/a.jpg")
        self.assertEqual(candidate_urls("https://cdn.example/a.jpg"), ["https://cdn.example/a.jpg"])


class FeedTests(unittest.TestCase):
    def test_parse_keeps_short_digest_and_drops_body(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
          <channel>
            <item>
              <title>一篇标题</title>
              <link>https://mp.weixin.qq.com/s?__biz=abc&amp;mid=1</link>
              <pubDate>Sat, 21 Nov 2026 00:54:00 +0800</pubDate>
              <description>一行摘要</description>
              <content:encoded><![CDATA[<p><img src="https://cdn.example/a.jpg?x=1&amp;y=2"></p><p>THIS_FULL_ARTICLE_SENTENCE_SHOULD_NOT_BE_STORED</p>]]></content:encoded>
            </item>
            <item>
              <title>摘要太长就不收</title>
              <link>https://mp.weixin.qq.com/s?id=2</link>
              <pubDate>Fri, 20 Nov 2026 08:00:00 +0800</pubDate>
              <description>这是一段超过四十二个字的描述，应该被丢掉，避免把正文摘要整段抄进笔记里。后面再补几个字。</description>
            </item>
          </channel>
        </rss>
        """
        items = parse_feed(xml.encode("utf-8"))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "一篇标题")
        self.assertEqual(items[0].day, "2026-11-21")
        self.assertEqual(items[0].published_text, "2026-11-21T00:54:00")
        self.assertEqual(items[0].digest, "一行摘要")
        self.assertEqual(items[0].link, "https://mp.weixin.qq.com/s?__biz=abc&mid=1")
        self.assertEqual(items[0].cover_url, "https://cdn.example/a.jpg?x=1&y=2")
        self.assertEqual(items[1].digest, "")
        blob = "\n".join(item.digest + item.title for item in items)
        self.assertNotIn(SENTINEL, blob)


class ArticleTests(unittest.TestCase):
    def test_stage_rules_and_cover_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            research = vault / "articles" / "2026-11-22-只有调研"
            research.mkdir(parents=True)
            (research / "调研.md").write_text("只是笔记\n", encoding="utf-8")

            writing = vault / "articles" / "2026-11-18-写了一半"
            writing.mkdir()
            (writing / "正文.md").write_text("写了几段，还没归档。\n", encoding="utf-8")
            write_png(writing / "shot.png", 8, 8, (20, 40, 60))

            done = vault / "articles" / "2026-11-20-写完了"
            done.mkdir()
            write_png(done / "cover.png", 8, 8, (90, 10, 10))
            write_png(done / "other.png", 8, 8, (10, 90, 10))
            (done / "正文.md").write_text(
                "---\ntitle: \"写完的标题\"\ndate: 2026-11-20\nsummary: \"一句摘要\"\n---\n\n![[cover.png]]\n",
                encoding="utf-8",
            )
            before = (done / "正文.md").read_bytes()

            stages = {item.folder.name: item for item in scan_articles(vault)}
            self.assertEqual(stages["2026-11-22-只有调研"].stage, "调研中")
            self.assertEqual(stages["2026-11-18-写了一半"].stage, "写作中")
            self.assertEqual(stages["2026-11-18-写了一半"].cover.name, "shot.png")
            self.assertEqual(stages["2026-11-20-写完了"].stage, "已完稿")
            self.assertEqual(stages["2026-11-20-写完了"].title, "写完的标题")
            self.assertEqual(stages["2026-11-20-写完了"].cover.name, "cover.png")

            from writing_dashboard.articles import write_article_index

            write_article_index(vault, stages["2026-11-20-写完了"])
            self.assertEqual((done / "正文.md").read_bytes(), before)
            index = (vault / "indexes" / "articles" / "2026-11-20-写完了.md").read_text(encoding="utf-8")
            self.assertIn("kind: \"article\"", index)
            self.assertIn("stage: \"已完稿\"", index)
            self.assertIn("cover.png", index)

    def test_shipped_examples(self):
        expected = {
            "2026-11-22-示例-选题从哪来": "调研中",
            "2026-11-18-示例-写了一半": "写作中",
            "2026-11-20-示例-把文章压成图文": "已完稿",
        }
        found = {item.folder.name: item for item in scan_articles(ROOT)}
        for name, stage in expected.items():
            self.assertEqual(found[name].stage, stage, name)
        self.assertIsNone(found["2026-11-22-示例-选题从哪来"].cover)
        self.assertIsNotNone(found["2026-11-18-示例-写了一半"].cover)
        self.assertEqual(found["2026-11-20-示例-把文章压成图文"].cover.name, "cover.png")
        self.assertEqual(found["2026-11-20-示例-把文章压成图文"].summary, "写完之后，挑能单独成立的几页，放进 social-cards，原文继续留在这里。")


class SocialTests(unittest.TestCase):
    def test_status_inference_and_drag_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            folder = vault / "social-cards" / "一套"
            folder.mkdir(parents=True)
            write_png(folder / "02.png", 8, 8, (1, 2, 3))
            write_png(folder / "01.png", 8, 8, (4, 5, 6))
            first = inspect_social(vault, folder)
            self.assertEqual(first.status, "制作中")
            self.assertEqual(first.pages, 2)
            self.assertEqual(first.cover.name, "01.png")
            from writing_dashboard.social import write_social_index

            write_social_index(vault, first)

            (folder / "文案.md").write_text("配文写好了。\n", encoding="utf-8")
            second = inspect_social(vault, folder)
            self.assertEqual(second.status, "待发布")
            write_social_index(vault, second)

            index = vault / "indexes" / "social" / "一套.md"
            text = index.read_text(encoding="utf-8")
            text = text.replace('status: "待发布"', 'status: "已发布"', 1)
            index.write_text(text, encoding="utf-8")
            dragged = inspect_social(vault, folder)
            self.assertEqual(dragged.status, "已发布")
            self.assertEqual(dragged.auto_status, "待发布")

            (folder / "文案.md").write_text("---\nstatus: \"制作中\"\n---\n\n还在改。\n", encoding="utf-8")
            explicit = inspect_social(vault, folder)
            self.assertEqual(explicit.status, "制作中")

    def test_shipped_examples(self):
        cases = {
            "示例-制作中-封面试排": ("制作中", 1),
            "示例-待发布-三页提纲": ("待发布", 3),
            "示例-已发布-一张就够": ("已发布", 1),
        }
        for name, (status, pages) in cases.items():
            record = inspect_social(ROOT, ROOT / "social-cards" / name)
            self.assertIsNotNone(record, name)
            self.assertEqual(record.status, status, name)
            self.assertEqual(record.pages, pages, name)


class CollectTests(unittest.TestCase):
    def test_collect_preserves_status_and_skips_full_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            now = datetime.now().astimezone().replace(microsecond=0)
            old = now - timedelta(days=40)
            feed = vault / "feed.xml"
            feed.write_text(
                f"""<?xml version="1.0" encoding="UTF-8"?>
                <rss><channel>
                  <item>
                    <title>今天的标题</title>
                    <link>https://mp.weixin.qq.com/s?id=keep</link>
                    <pubDate>{format_datetime(now)}</pubDate>
                    <description>短摘要</description>
                    <content:encoded xmlns:content="http://purl.org/rss/1.0/modules/content/"><![CDATA[<p>{SENTINEL}</p>]]></content:encoded>
                  </item>
                  <item>
                    <title>太早的</title>
                    <link>https://mp.weixin.qq.com/s?id=old</link>
                    <pubDate>{format_datetime(old)}</pubDate>
                    <description>旧</description>
                  </item>
                </channel></rss>
                """,
                encoding="utf-8",
            )
            config = {"since_days": 14, "per_account": 12, "accounts": [{"name": "卡兹克", "feeds": [str(feed)]}]}
            report = collect_accounts(vault, config, skip_covers=True)
            self.assertEqual(report.results[0].created, 1)
            self.assertEqual(report.results[0].skipped, 1)
            note = next((vault / "topic-radar" / "items").glob("*.md"))
            text = note.read_text(encoding="utf-8")
            self.assertNotIn(SENTINEL, text)
            self.assertIn('status: "待看"', text)
            self.assertIn("短摘要", text)
            data, body = split_note(text)
            data["status"] = "可借鉴"
            note.write_text(render_note(data, body + "\n我的批注", list(data)), encoding="utf-8")
            feed.write_text(feed.read_text(encoding="utf-8").replace("今天的标题", "改过的标题"), encoding="utf-8")
            again = collect_accounts(vault, config, skip_covers=True)
            self.assertEqual(again.results[0].updated, 1)
            updated = note.read_text(encoding="utf-8")
            self.assertIn("改过的标题", updated)
            self.assertIn('status: "可借鉴"', updated)
            self.assertIn("我的批注", updated)
            self.assertNotIn(SENTINEL, updated)


class SyncTests(unittest.TestCase):
    def test_index_removes_stale_notes_and_keeps_follow_list_preamble(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "scripts").mkdir()
            (vault / "scripts" / "accounts.json").write_text(
                json.dumps({"accounts": [{"name": "空格", "feeds": []}]}),
                encoding="utf-8",
            )
            folder = vault / "articles" / "2026-01-01-暂时"
            folder.mkdir(parents=True)
            (folder / "调研.md").write_text("笔记\n", encoding="utf-8")
            sync_vault(vault, index_only=True)
            stale = vault / "indexes" / "articles" / "不存在了.md"
            stale.write_text("旧索引\n", encoding="utf-8")
            shutil.rmtree(folder)
            _, article_count, _ = sync_vault(vault, index_only=True)
            self.assertEqual(article_count, 0)
            self.assertFalse(stale.exists())

            sync_vault(vault, collect_only=True)
            follow = vault / "topic-radar" / "关注列表.md"
            follow.write_text("# 关注列表\n\n手写的一句。\n\n<!-- sync:start -->\n旧\n<!-- sync:end -->\n\n结尾留着。\n", encoding="utf-8")
            sync_vault(vault, collect_only=True)
            text = follow.read_text(encoding="utf-8")
            self.assertIn("手写的一句。", text)
            self.assertIn("结尾留着。", text)
            self.assertIn("空格", text)
            self.assertNotIn("旧", text)


class ScaffoldTests(unittest.TestCase):
    def test_new_folders_land_in_the_right_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            article = create_article(vault, "一个题目", day="2026-11-23")
            social = create_social(vault, "一套新的")
            self.assertTrue((article / "调研.md").is_file())
            self.assertFalse((article / "正文.md").exists())
            record = inspect_article(article)
            self.assertEqual(record.stage, "调研中")
            self.assertEqual(inspect_social(vault, social).status, "制作中")


class BaseFileTests(unittest.TestCase):
    def test_base_files_are_yaml_and_cover_the_boards(self):
        expected = {
            "统计.base": {"今日同行更新", "待看文章", "小红书图文", "已完稿文章"},
            "同行文章.base": {"最近 7 天", "今天", "全部"},
            "阅读进度.base": {"阅读进度", "选题池"},
            "小红书图文.base": {"图文", "发布进度"},
            "我的文章.base": {"时间线", "按年份", "写作进度"},
        }
        for name, views in expected.items():
            data = yaml.safe_load((ROOT / "bases" / name).read_text(encoding="utf-8"))
            self.assertEqual({item["name"] for item in data["views"]}, views, name)
        reading = yaml.safe_load((ROOT / "bases" / "阅读进度.base").read_text(encoding="utf-8"))
        kanban = reading["views"][0]
        self.assertEqual(kanban["type"], "kanban")
        self.assertEqual(kanban["groupBy"]["property"], "note.status")
        self.assertEqual(kanban["groupOrder"], ["待看", "可借鉴", "已看"])
        writing = yaml.safe_load((ROOT / "bases" / "我的文章.base").read_text(encoding="utf-8"))
        progress = next(item for item in writing["views"] if item["name"] == "写作进度")
        self.assertEqual(progress["groupBy"]["property"], "formula.stage_col")
        social = yaml.safe_load((ROOT / "bases" / "小红书图文.base").read_text(encoding="utf-8"))
        self.assertGreater(social["views"][0]["imageAspectRatio"], 1)


if __name__ == "__main__":
    unittest.main()
