import enum
from abc import ABC, abstractmethod
from pathlib import Path

from cibot.backends.base import CiBotBackendBase, ReleaseInfo
from cibot.storage_layers.base import BaseStorage


class ShouldRelease(enum.Enum):
	YES = "yes"
	ABSTAIN = "abstain"


class BumpType(enum.Enum):
	MINOR = "minor"
	MAJOR = "major"
	PATCH = "patch"


class CiBotPlugin(ABC):
	def __init__(self, backend: CiBotBackendBase, storage: BaseStorage) -> None:
		self.backend = backend
		self.storage = storage
		self._pr_comment: str | None = None
		self._should_fail_work_flow = False
		if "*" not in self.supported_backends() and backend.name() not in self.supported_backends():
			raise ValueError(f"Backend {backend.name()} is not supported by this plugin")

	def on_pr_changed(self, pr: int) -> BumpType | None:
		return None

	def on_commit_to_main(self, commit_hash: str) -> None | ReleaseInfo:
		return None

	def prepare_release(self, release_type: BumpType, next_version: str) -> list[Path]:
		return []

	@abstractmethod
	def plugin_name(self) -> str: ...

	@abstractmethod
	def supported_backends(self) -> tuple[str, ...]: ...

	def pr_comment_id(self) -> str:
		return f"popo kaka baba jojo {self.plugin_name()}"

	def provide_comment_for_pr(self) -> tuple[str, str] | None:
		"""
		Get the comment from the PR description.

		this would be used in conjunction with the plugin name in the bot comment.
		"""
		if self._pr_comment:
			return self._pr_comment, self.pr_comment_id()
		return None

	def should_fail_workflow(self) -> bool:
		"""
		Return True if the workflow should fail, False otherwise.
		"""
		return self._should_fail_work_flow


class VersionBumpPlugin(CiBotPlugin):
	@abstractmethod
	def next_version(self, bump_type: BumpType) -> str:
		raise NotImplementedError("Subclasses must implement this method")
