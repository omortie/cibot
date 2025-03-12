from abc import ABC, abstractmethod
import subprocess

from msgspec import Struct

from cibot.storage_layers.base import BaseStorage


class PRContributor(Struct):
    pr_number: int
    pr_author_username: str
    pr_author_fullname: str | None


class PrDescription(Struct):
    contributor: PRContributor
    header: str
    description: str
    pr_number: int


class CiBotBackendBase(ABC):
    def __init__(self, storage: BaseStorage) -> None:
        super().__init__()

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def create_pr_comment(self, content: str) -> None: ...

    @abstractmethod
    def publish_release(self, project_name: str, version: str) -> None: ...

    def git(self, *args: str) -> None:
        return subprocess.run(["git", *args], check=False).check_returncode()

    @abstractmethod
    def get_pr_description(self, pr_number: int) -> PrDescription: ...

    @abstractmethod
    def get_commit_associated_pr(self, commit_hash: str) -> PrDescription: ...

    @abstractmethod
    def get_pr_labels(self, pr_number: int) -> list[str]: ...

    def get_current_commit_hash(self) -> str:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"], check=True, capture_output=True
            )
            .stdout.decode()
            .strip()
        )

    def configure_git(self, username: str, email: str) -> None:
        self.git("config", "user.name", username)
        self.git("config", "user.email", email)
