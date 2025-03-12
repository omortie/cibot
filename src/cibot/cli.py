from functools import cache
import os
from pathlib import Path
from typing import TYPE_CHECKING
import jinja2
from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict
from typer import Typer

from cibot.backends.base import CiBotBackendBase
from cibot.plugins.base import CiBotPlugin
from cibot.storage_layers.base import BaseStorage

from .plugins.deferred_release import DeferredReleasePlugin

if TYPE_CHECKING:
    from github.Repository import Repository


app = Typer(name="management")
template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=jinja2.select_autoescape(),
)

BOT_COMMENT_TEMPLATE = template_env.get_template("bot_comment.jinja.md")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(cli_prefix="CIBOT")

    BACKEND: str = "github"
    STORAGE: str = "github_issue"
    PLUGINS: list[str] = []


class GithubSettings(BaseSettings):
    model_config = SettingsConfigDict(cli_prefix="CIBOT_GITHUB")
    TOKEN: str | None = None
    STORAGE_ISSUE_NUMBER: int | None = None
    REPO_SLUG: str | None = None


@cache
def get_github_repo() -> "Repository":
    from github import Github

    settings = GithubSettings()
    if not settings.TOKEN:
        raise ValueError("missing GITHUB_TOKEN")
    if not settings.REPO_SLUG:
        raise ValueError("missing GITHUB_REPO_SLUG")
    client = Github(settings.TOKEN)
    return client.get_repo(settings.REPO_SLUG)


def get_storage() -> BaseStorage:
    settings = Settings()
    match settings.STORAGE:
        case "github_issue":
            from cibot.storage_layers.github_issue import GithubIssueStorage

            gh_settings = GithubSettings()
            repo = get_github_repo()
            if not gh_settings.STORAGE_ISSUE_NUMBER:
                raise ValueError("missing STORAGE_ISSUE_NUMBER")
            issue = (
                repo.get_issue(gh_settings.STORAGE_ISSUE_NUMBER)
                .get_comments()
                .get_page(0)[0]
            )
            return GithubIssueStorage(issue)
        case _:
            raise ValueError(f"Unknown storage {settings.STORAGE}")


def get_backend() -> CiBotBackendBase:
    backend_name = os.environ.get("BACKEND")
    if not backend_name:
        raise ValueError("BACKEND environment variable is not set")
    match backend_name:
        case "github":
            from cibot.backends.github_backend import GithubBackend

            repo = get_github_repo()
            storage = get_storage()
            return GithubBackend(repo, storage)
        case _:
            raise ValueError(f"Unknown backend {backend_name}")


PLUGINS_REGISTRY = {
    "deferred_release": DeferredReleasePlugin,
}


def get_plugins(backend: CiBotBackendBase, storage: BaseStorage) -> list[CiBotPlugin]:
    settings = Settings()
    out = []
    for name in settings.PLUGINS:
        logger.info(f"Loading plugin {name}")
        out.append(PLUGINS_REGISTRY[name](backend, storage))
        if name not in PLUGINS_REGISTRY:
            raise ValueError(f"Unknown plugin {name}")
    return out


class PluginRunner:
    def __init__(self, backend: CiBotBackendBase, storage: BaseStorage) -> None:
        self.backend = backend
        self.storage = storage
        self.plugins = get_plugins(backend, storage)
        self.backend.configure_git("cibot", "cibot@no.reply")

    def on_pr_changed(self, pr: int):
        for plugin in self.plugins:
            plugin.on_pr_changed(pr)

    def on_commit_to_main(self):
        for plugin in self.plugins:
            plugin.on_commit_to_main(self.backend.get_current_commit_hash())


def get_runner() -> PluginRunner:
    backend = get_backend()
    storage = get_storage()
    return PluginRunner(backend, storage)


@app.command()
def on_pr_changed(pr: int):
    runner = get_runner()
    runner.on_pr_changed(pr)


@app.command()
def on_commit_to_main():
    runner = get_runner()
    runner.on_commit_to_main()


if __name__ == "__main__":
    app()
