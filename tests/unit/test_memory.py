"""Tests for ConversationMemory."""

from __future__ import annotations

from hermes.core.memory import ConversationMemory


class TestConversationMemory:
    def test_create_new_session(self):
        mem = ConversationMemory()
        session = mem.get_or_create_session()
        assert session.session_id
        assert session.messages == []

    def test_create_session_with_id(self):
        mem = ConversationMemory()
        session = mem.get_or_create_session("abc123")
        assert session.session_id == "abc123"

    def test_get_existing_session(self):
        mem = ConversationMemory()
        s1 = mem.get_or_create_session("abc123")
        s2 = mem.get_or_create_session("abc123")
        assert s1 is s2

    def test_add_and_get_history(self):
        mem = ConversationMemory()
        session = mem.get_or_create_session("s1")
        session.add("human", "Hello!")
        session.add("ai", "Hi there!")
        history = session.get_history()
        assert history == [("human", "Hello!"), ("ai", "Hi there!")]

    def test_history_trimmed_to_max(self):
        mem = ConversationMemory()
        session = mem.get_or_create_session("s1")
        session.max_history = 4
        for i in range(10):
            session.add("human", f"msg-{i}")
        assert len(session.messages) == 4
        assert session.messages[-1].content == "msg-9"

    def test_list_sessions(self):
        mem = ConversationMemory()
        mem.get_or_create_session("a")
        mem.get_or_create_session("b")
        assert set(mem.list_sessions()) == {"a", "b"}

    def test_delete_session(self):
        mem = ConversationMemory()
        mem.get_or_create_session("a")
        assert mem.delete_session("a") is True
        assert mem.get_session("a") is None

    def test_delete_nonexistent(self):
        mem = ConversationMemory()
        assert mem.delete_session("nope") is False

    def test_clear_session(self):
        mem = ConversationMemory()
        session = mem.get_or_create_session("s1")
        session.add("human", "test")
        session.clear()
        assert session.messages == []
