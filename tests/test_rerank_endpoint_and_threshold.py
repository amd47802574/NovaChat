"""精排端点拼接与准入门槛的回归测试。

背景：RERANK_BINDING_HOST 配成 https://api.siliconflow.cn/v1 时，
旧逻辑会拼出 /v1/v1/rerank 导致 404，精排静默降级为 RRF 排序，
不相关文件的片段因此进入上下文。
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_utils(env: dict | None = None):
    """以桩件加载 backend/rag/utils.py，避开 embedding / Milvus 启动开销。"""
    fake_indexing = types.ModuleType("backend.indexing")
    fake_indexing.__path__ = []

    fake_milvus = types.ModuleType("backend.indexing.milvus_client")
    fake_milvus.get_milvus_store = lambda: object()

    fake_embedding = types.ModuleType("backend.indexing.embedding")
    fake_embedding.embedding_service = object()

    fake_parent = types.ModuleType("backend.indexing.parent_chunk_store")

    class _ParentChunkStore:
        def get_documents_by_ids(self, ids):
            return []

    fake_parent.ParentChunkStore = _ParentChunkStore

    stubs = {
        "backend.indexing": fake_indexing,
        "backend.indexing.milvus_client": fake_milvus,
        "backend.indexing.embedding": fake_embedding,
        "backend.indexing.parent_chunk_store": fake_parent,
    }
    previous_mods = {key: sys.modules.get(key) for key in stubs}
    previous_env = {key: __import__("os").environ.get(key) for key in (env or {})}

    import os

    for key, value in (env or {}).items():
        os.environ[key] = value
    sys.modules.update(stubs)

    module_name = f"rag_utils_under_test_{id(env)}"
    spec = importlib.util.spec_from_file_location(
        module_name, REPO_ROOT / "backend" / "rag" / "utils.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        for key, value in previous_mods.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        sys.modules.pop(module_name, None)
    return module


class RerankEndpointTests(unittest.TestCase):
    def test_host_ending_with_v1_does_not_double_prefix(self):
        """回归：/v1 结尾的 host 不能拼成 /v1/v1/rerank。"""
        utils = load_utils({"RERANK_BINDING_HOST": "https://api.siliconflow.cn/v1"})
        self.assertEqual(
            "https://api.siliconflow.cn/v1/rerank", utils._get_rerank_endpoint()
        )

    def test_bare_host_gets_full_suffix(self):
        utils = load_utils({"RERANK_BINDING_HOST": "https://api.siliconflow.cn"})
        self.assertEqual(
            "https://api.siliconflow.cn/v1/rerank", utils._get_rerank_endpoint()
        )

    def test_full_rerank_path_is_preserved(self):
        utils = load_utils(
            {"RERANK_BINDING_HOST": "https://api.siliconflow.cn/v1/rerank"}
        )
        self.assertEqual(
            "https://api.siliconflow.cn/v1/rerank", utils._get_rerank_endpoint()
        )

    def test_trailing_slash_is_normalized(self):
        utils = load_utils({"RERANK_BINDING_HOST": "https://api.siliconflow.cn/v1/"})
        self.assertEqual(
            "https://api.siliconflow.cn/v1/rerank", utils._get_rerank_endpoint()
        )

    def test_empty_host_returns_empty(self):
        utils = load_utils({"RERANK_BINDING_HOST": ""})
        self.assertEqual("", utils._get_rerank_endpoint())


class RerankMinScoreTests(unittest.TestCase):
    def test_threshold_filters_low_scoring_rerank_docs(self):
        """精排分低于门槛的片段（跨文件噪音）必须被过滤。"""
        utils = load_utils({"RERANK_MIN_SCORE": "0.01"})
        self.assertTrue(utils._meets_rerank_min_score({"rerank_score": 0.99}))
        self.assertTrue(utils._meets_rerank_min_score({"rerank_score": 0.01}))
        self.assertFalse(utils._meets_rerank_min_score({"rerank_score": 0.000016}))
        self.assertFalse(utils._meets_rerank_min_score({"rerank_score": 0.002}))

    def test_threshold_does_not_apply_to_recall_scores(self):
        """回归：精排降级时只有 RRF 召回分，不能被精排门槛误杀。"""
        utils = load_utils({"RERANK_MIN_SCORE": "0.01"})
        # RRF 融合分量级约 0.016，且与语义相关性无关，放行。
        self.assertTrue(utils._meets_rerank_min_score({"score": 0.0163}))
        self.assertTrue(utils._meets_rerank_min_score({"score": 0.0001}))
        self.assertTrue(utils._meets_rerank_min_score({}))

    def test_zero_threshold_disables_filtering(self):
        utils = load_utils({"RERANK_MIN_SCORE": "0.0"})
        self.assertTrue(utils._meets_rerank_min_score({"rerank_score": 0.0}))
        self.assertTrue(utils._meets_rerank_min_score({"rerank_score": 0.000016}))


class RerankAppliedFlagTests(unittest.TestCase):
    def _docs(self):
        return [
            {"text": "高空抛物责任规定", "chunk_id": "law-7"},
            {"text": "简历 ATS 适配规范", "chunk_id": "resume-6"},
        ]

    def _utils_with_rerank(self):
        return load_utils(
            {
                "RERANK_MODEL": "BAAI/bge-reranker-v2-m3",
                "RERANK_API_KEY": "test-key",
                "RERANK_BINDING_HOST": "https://api.siliconflow.cn/v1",
                "RERANK_MIN_SCORE": "0.01",
            }
        )

    def test_http_error_reports_not_applied(self):
        """回归：404 时 rerank_applied 必须为 False，否则故障不可见。"""
        utils = self._utils_with_rerank()

        class FakeResponse:
            status_code = 404
            text = "Not Found"

        utils.requests = types.SimpleNamespace(
            post=lambda *a, **kw: FakeResponse(),
            RequestException=Exception,
        )

        docs, meta = utils._rerank_documents("高空抛物致人受伤谁担责", self._docs(), 8)
        self.assertTrue(meta["rerank_enabled"])
        self.assertFalse(meta["rerank_applied"])
        self.assertIn("404", meta["rerank_error"])
        self.assertEqual(2, len(docs))

    def test_successful_rerank_applies_scores_and_filters(self):
        utils = self._utils_with_rerank()

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "results": [
                        {"index": 0, "relevance_score": 0.99},
                        {"index": 1, "relevance_score": 0.000016},
                    ]
                }

        utils.requests = types.SimpleNamespace(
            post=lambda *a, **kw: FakeResponse(),
            RequestException=Exception,
        )

        reranked, meta = utils._rerank_documents(
            "高空抛物致人受伤谁担责", self._docs(), 8
        )
        self.assertTrue(meta["rerank_applied"])
        self.assertIsNone(meta["rerank_error"])

        # 门槛过滤后只应保留法律片段，简历片段被剔除。
        final = [d for d in reranked if utils._meets_rerank_min_score(d)]
        self.assertEqual(1, len(final))
        self.assertEqual("law-7", final[0]["chunk_id"])


if __name__ == "__main__":
    unittest.main()
