from abc import ABC, abstractmethod
from dataclasses import dataclass
import enum
from pathlib import Path
from typing import AbstractSet, ClassVar

from cibot.backends.base import CiBotBackendBase
from cibot.storage_layers.base import BaseStorage


class ShouldRelease(enum.Enum):
	YES = "yes"
	ABSTAIN = "abstain"


class BumpType(enum.Enum):
	MINOR = "minor"
	MAJOR = "major"
	PATCH = "patch"

@dataclass
class ReleaseInfo:
	note: str
	

class CiBotPlugin(ABC):
	supported_backednds: ClassVar[tuple[str, ...]]

	def __init__(self, backend: CiBotBackendBase, storage: BaseStorage) -> None:
		self.backend = backend
		self.storage = storage
		self._pr_comment: str | None = None
		self._should_fail_work_flow = False
		if backend.name() not in self.supported_backednds:
			raise ValueError(f"Backend {backend.name} is not supported by this plugin")

	def on_pr_changed(self, pr: int) -> BumpType | None:
		return None

	def on_commit_to_main(self, commit_hash: str) -> None | ReleaseInfo:
		return None

	def prepare_release(self, release_type: BumpType, next_version: str) -> list[Path]:
		return []


	@abstractmethod
	def plugin_name(self) -> str: ...

	def provide_comment_for_pr(self) -> str | None:
		"""
		Get the comment from the PR description.

		this would be used in conjunction with the plugin name in the bot comment.
		"""
		return self._pr_comment
		
	def should_fail_workflow(self) -> bool:
		"""
		Return True if the workflow should fail, False otherwise.
		"""
		return self._should_fail_work_flow


class VersionBumpPlugin(CiBotPlugin):
	@abstractmethod
	def next_version(self, bump_type: BumpType) -> str:
		raise NotImplementedError("Subclasses must implement this method")
