from __future__ import annotations

import streamlit as st

from src.core.auth import (
    count_users,
    create_user,
    ensure_users_table,
    verify_credentials,
)
from src.frontend.shared import run_async


def ensure_setup() -> None:
    run_async(ensure_users_table())


def get_user_count() -> int:
    @st.cache_data(show_spinner=False)
    def _cached_count() -> int:
        return run_async(count_users())

    return _cached_count()


def create_first_user(username: str, password: str, *, full_name: str, email: str) -> None:
    run_async(
        create_user(
            username.strip(),
            password,
            full_name=full_name.strip(),
            email=email.strip(),
            role="ADMIN",
        )
    )


def check_credentials(username: str, password: str) -> tuple[bool, str | None]:
    ok, user = run_async(verify_credentials(username.strip(), password))
    return ok, user["username"] if ok and user else None
