import json
import unittest
from unittest.mock import patch

from amon.tooling.builtins.web import WebPolicy, WebSearchOptions, handle_web_better_search, handle_web_search
from amon.tooling.types import ToolCall


class WebSearchFallbackTests(unittest.TestCase):
    def test_web_search_fallback_to_builtin_google_when_serpapi_missing(self) -> None:
        call = ToolCall(tool="web.search", args={"query": "台灣 AI 新聞", "max_results": 3})
        with patch(
            "amon.tooling.builtins.web._search_with_serpapi",
            return_value=([], "missing_key"),
        ), patch(
            "amon.tooling.builtins.web._search_with_google_builtin",
            return_value=([{"title": "A", "url": "https://example.com/a"}], "ok"),
        ):
            result = handle_web_search(call, policy=WebPolicy(), options=WebSearchOptions())

        self.assertFalse(result.is_error)
        self.assertEqual(result.meta.get("provider"), "google")
        payload = json.loads(result.as_text())
        self.assertEqual(payload[0]["url"], "https://example.com/a")

    def test_web_search_returns_error_when_all_providers_empty(self) -> None:
        call = ToolCall(tool="web.search", args={"query": "x", "max_results": 2})
        with patch("amon.tooling.builtins.web._search_with_serpapi", return_value=([], "quota_exceeded")), patch(
            "amon.tooling.builtins.web._search_with_google_builtin", return_value=([], "empty")
        ), patch("amon.tooling.builtins.web._search_with_bing_builtin", return_value=([], "empty")):
            result = handle_web_search(call, policy=WebPolicy(), options=WebSearchOptions())

        self.assertTrue(result.is_error)
        self.assertEqual(result.meta.get("status"), "empty")


class BetterSearchTests(unittest.TestCase):
    def test_better_search_merges_distinct_urls(self) -> None:
        call = ToolCall(tool="web.better_search", args={"query": "python typing", "max_results": 4})

        def fake_search(query: str, *, max_results: int, policy: WebPolicy, options: WebSearchOptions):
            return (
                [
                    {"title": f"{query}-1", "url": "https://example.com/shared"},
                    {"title": f"{query}-2", "url": f"https://example.com/{query}"},
                ],
                "google",
            )

        with patch("amon.tooling.builtins.web._search_with_priority", side_effect=fake_search):
            result = handle_web_better_search(call, policy=WebPolicy(), options=WebSearchOptions())

        self.assertFalse(result.is_error)
        payload = json.loads(result.as_text())
        urls = [item["url"] for item in payload]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertTrue(all("strategy_query" in item for item in payload))


if __name__ == "__main__":
    unittest.main()
