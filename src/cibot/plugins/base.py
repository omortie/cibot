import enum
from typing import ClassVar

from cibot.backends.base import CiBotBackendBase
from cibot.storage_layers.base import BaseStorage


class ShouldRelease(enum.Enum):
    YES = "yes"
    ABSTAIN = "abstain"


class ReleaseType(enum.Enum):
    MINOR = "minor"
    MAJOR = "major"
    PATCH = "patch"


class CiBotPlugin:
    supported_backednds: ClassVar[tuple[str, ...]]

    def __init__(self, backend: CiBotBackendBase, storage: BaseStorage) -> None:
        self.backend = backend
        self.storage = storage
        if backend.name() not in self.supported_backednds:
            raise ValueError(f"Backend {backend.name} is not supported by this plugin")

    def on_pr_changed(self, pr: int) -> None: ...

    def on_commit_to_main(self, commit_hash: str) -> ReleaseType | None:
        return None

    def prepare_release(self, release_type: ReleaseType) -> None: ...

    def release(self, release_type: ReleaseType) -> None: ...

    def plugin_name(self) -> str: ...

    def provide_comment_for_pr(self) -> str | None:
        """
        Get the comment from the PR description.

        this would be used in conjunction with the plugin name in the bot comment.
        """
