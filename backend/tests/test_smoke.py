"""冒烟测试：注册登录 → 会话流式问答 → 生成文章（红线：author 绑定）"""
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture()
async def client():
    from app.db.session import close_db, init_db
    await init_db()  # ASGITransport 不触发 lifespan，显式建表
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await close_db()


async def _token(client: AsyncClient, suffix: str) -> tuple[str, str]:
    username = f"smoke_{suffix}_{uuid.uuid4().hex[:8]}"  # 唯一用户名，测试可重复执行
    resp = await client.post("/api/v1/auth/register", json={
        "username": username, "password": "pass123456",
    })
    return resp.json()["data"]["token"], username


@pytest.mark.asyncio
async def test_register_login_me(client: AsyncClient):
    token, username = await _token(client, "auth")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["username"] == username


@pytest.mark.asyncio
async def test_models_are_loaded_from_database(client: AsyncClient):
    resp = await client.get("/api/v1/models")
    assert resp.json()["code"] == 0
    assert any(model["id"] == "doubao-lite" for model in resp.json()["data"])


@pytest.mark.asyncio
async def test_chat_stream(client: AsyncClient):
    token, _ = await _token(client, "chat")
    headers = {"Authorization": f"Bearer {token}"}
    session = (await client.post("/api/v1/sessions", headers=headers)).json()["data"]
    resp = await client.post(
        f"/api/v1/sessions/{session['id']}/chat/stream",
        headers=headers, json={"content": "海淀幼升小政策", "model_id": "doubao-lite"},
    )
    assert resp.status_code == 200
    assert "event: message_delta" in resp.text and "event: task_progress" in resp.text
    assert "citations" in resp.text or "引用" in resp.text


@pytest.mark.asyncio
async def test_generate_article_author_binding(client: AsyncClient):
    token, _ = await _token(client, "gen")
    headers = {"Authorization": f"Bearer {token}"}
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()["data"]
    resp = await client.post(
        "/api/v1/articles/generate", headers=headers,
        json={"topic": "海淀幼升小攻略", "model_id": "doubao-pro"},
    )
    assert resp.text.count("event: message_delta") > 1
    done_block = next(block for block in resp.text.split("\n\n") if '"stage": "done"' in block)
    data = json.loads(done_block.split("data: ", 1)[1])["article"]
    # 全局红线 4：文章强制绑定当前账号
    assert data["author_id"] == me["id"] and data["status"] == "draft"
    pub = (await client.post(f"/api/v1/articles/{data['id']}/publish", headers=headers)).json()["data"]
    assert pub["status"] == "published"
    mine = (await client.get("/api/v1/articles/mine", headers=headers)).json()["data"]
    assert any(a["id"] == data["id"] for a in mine)
