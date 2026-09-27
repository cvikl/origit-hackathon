"""Settings from environment (see .env.example). Nothing here reads a file; docker compose / uvicorn pass the env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    data_dir: str = field(default_factory=lambda: os.path.abspath(os.environ.get("ORIGIT_DATA_DIR", "./data")))
    token: str = field(default_factory=lambda: os.environ.get("CONSOLE_TOKEN", ""))
    bob_api_key: str = field(default_factory=lambda: os.environ.get("BOB_API_KEY", ""))
    bob_max_cost: float = field(default_factory=lambda: float(os.environ.get("BOB_MAX_COST", "0.5")))
    bob_max_turns: int = field(default_factory=lambda: int(os.environ.get("BOB_MAX_TURNS", "6")))
    bob_timeout: int = field(default_factory=lambda: int(os.environ.get("BOB_TIMEOUT", "240")))
    public_url: str = field(default_factory=lambda: os.environ.get("PUBLIC_URL", "http://localhost:8787").rstrip("/"))
    git_ssh_host: str = field(default_factory=lambda: os.environ.get("GIT_SSH_HOST", "git@origit.uk"))
    git_ssh_root: str = field(default_factory=lambda: os.environ.get("GIT_SSH_ROOT", "/srv/origit/repos"))
    hook_url: str = field(default_factory=lambda: os.environ.get("HOOK_URL", "http://127.0.0.1:8787/api/hooks/post-receive"))
    github_url: str = field(default_factory=lambda: os.environ.get("GITHUB_URL", "https://github.com/cvikl/origit"))
    readonly: bool = field(default_factory=lambda: os.environ.get("CONSOLE_READONLY", "0").lower() in ("1", "true", "yes"))
    demo_account: str = field(default_factory=lambda: os.environ.get("DEMO_ACCOUNT", ""))
    prompts_dir: str = field(default_factory=lambda: os.path.abspath(os.environ.get("PROMPTS_DIR", os.path.join(os.path.dirname(__file__), "..", "prompts"))))
    seed_dir: str = field(default_factory=lambda: os.path.abspath(os.environ.get("SEED_DIR", os.path.join(os.path.dirname(__file__), "..", "seed"))))

    @property
    def repos_dir(self) -> str:
        return os.path.join(self.data_dir, "repos")

    @property
    def state_dir(self) -> str:
        return os.path.join(self.data_dir, "state")


settings = Settings()
