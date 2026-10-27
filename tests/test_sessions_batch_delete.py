import asyncio
import importlib
import json
import unittest
from datetime import datetime, timezone

import httpx
from langchain_core.messages import HumanMessage

storage_module = importlib.import_module("backend.chat.storage")
storage = storage_module.storage
ConversationStorage = storage_module.ConversationStorage

from backend.infra.database import SessionLocal, init_db  # noqa: E402
from backend.db.models import User  # noqa: E402


def _make_unique_username(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def _ensure_user(username: str) -> None:
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == username).first():
            db.add(User(username=username, password_hash="test", role="user"))
            db.commit()
    finally:
        db.close()


def _create_session(username: str, session_id: str, title: str) -> None:
    storage.save(
        username,
        session_id,
        [HumanMessage(content=f"{title} 的第一条消息")],
        metadata={"title": title, "pinned": False},
    )


class BatchDeleteStorageTest(unittest.TestCase):
    """校验 storage.delete_sessions_batch 能批量删除指定会话且不影响其它会话。"""

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.username = _make_unique_username("batch_store")
        _ensure_user(self.username)
        self.ids = [f"{self.username}_s1", f"{self.username}_s2", f"{self.username}_s3"]
        for idx, sid in enumerate(self.ids, start=1):
            _create_session(self.username, sid, f"会话{idx}")
        # 确保列表缓存已写入。
        self.assertIn(len(storage.list_sessions(self.username)), (3,))

    def tearDown(self):
        # 清理可能残留的会话。
        storage.delete_sessions_batch(self.username, self.ids)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == self.username).first()
            if user:
                db.delete(user)
                db.commit()
        finally:
            db.close()

    def test_deletes_only_requested_sessions(self):
        deleted = storage.delete_sessions_batch(self.username, [self.ids[0], self.ids[2]])
        self.assertEqual(deleted, 2)
        remaining = storage.list_sessions(self.username)
        self.assertEqual(remaining, [self.ids[1]])

    def test_ignores_nonexistent_ids(self):
        deleted = storage.delete_sessions_batch(
            self.username, [self.ids[0], "not_exist_1", "not_exist_2"]
        )
        self.assertEqual(deleted, 1)
        remaining = storage.list_sessions(self.username)
        self.assertEqual(set(remaining), {self.ids[1], self.ids[2]})

    def test_dedupes_repeated_ids(self):
        deleted = storage.delete_sessions_batch(self.username, [self.ids[0], self.ids[0]])
        self.assertEqual(deleted, 1)

    def test_empty_input_is_noop(self):
        self.assertEqual(storage.delete_sessions_batch(self.username, []), 0)
        self.assertEqual(storage.delete_sessions_batch(self.username, ["", None]), 0)  # type: ignore

    def test_other_users_sessions_are_untouched(self):
        other = _make_unique_username("batch_other")
        _ensure_user(other)
        _create_session(other, f"{other}_only", "他人会话")
        try:
            storage.delete_sessions_batch(self.username, self.ids)
            self.assertEqual(storage.list_sessions(self.username), [])
            self.assertEqual(storage.list_sessions(other), [f"{other}_only"])
        finally:
            storage.delete_sessions_batch(other, [f"{other}_only"])
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == other).first()
                if user:
                    db.delete(user)
                    db.commit()
            finally:
                db.close()


class BatchDeleteRouteTest(unittest.TestCase):
    """校验 DELETE /sessions/batch 路由的鉴权、入参与返回。

    Starlette/httpx 0.28 的 delete 不支持请求体，这里改用 httpx.ASGITransport
    直接驱动 ASGI 应用，从而能在 DELETE 请求中携带 JSON body 与 Bearer 令牌。
    """

    @classmethod
    def setUpClass(cls):
        init_db()
        from backend.api.routes.sessions import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        cls.app = app

    async def _call_delete(self, payload, token=None):
        transport = httpx.ASGITransport(app=self.app)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # httpx 0.28 的 delete 不接受请求体，改用通用 request 发送 DELETE body。
            return await client.request(
                "DELETE",
                "/sessions/batch",
                content=json.dumps(payload),
                headers=headers,
            )

    def setUp(self):
        from backend.infra.auth import create_access_token

        self.username = _make_unique_username("batch_route")
        _ensure_user(self.username)
        self.ids = [f"{self.username}_r1", f"{self.username}_r2"]
        for sid in self.ids:
            _create_session(self.username, sid, "路由测试会话")
        self.token = create_access_token(self.username, "user")

    def tearDown(self):
        storage.delete_sessions_batch(self.username, self.ids)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == self.username).first()
            if user:
                db.delete(user)
                db.commit()
        finally:
            db.close()

    def test_batch_delete_returns_count(self):
        resp = asyncio.run(self._call_delete({"session_ids": self.ids}, token=self.token))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["deleted_count"], 2)
        self.assertEqual(storage.list_sessions(self.username), [])

    def test_requires_authentication(self):
        resp = asyncio.run(self._call_delete({"session_ids": self.ids}))
        self.assertEqual(resp.status_code, 401)

    def test_empty_payload_is_400(self):
        resp = asyncio.run(self._call_delete({"session_ids": []}, token=self.token))
        self.assertEqual(resp.status_code, 400)

    def test_batch_route_does_not_match_single_delete(self):
        # "batch" 不应被当成 session_id 落到单条删除路由。
        resp = asyncio.run(self._call_delete({"session_ids": ["batch"]}, token=self.token))
        self.assertNotEqual(resp.status_code, 404)
        self.assertIn("deleted_count", resp.json())


if __name__ == "__main__":
    unittest.main()
