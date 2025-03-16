import datetime
import enum
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import ClassVar, override

import msgspec
from loguru import logger

from cibot.backends.base import ERROR_GIF, PrDescription
from cibot.plugins.base import BumpType, CiBotPlugin, ReleaseInfo
from cibot.settings import GithubSettings


class ChangeType(enum.Enum):
	FEATURE = "Feature"
	BUG_FIX = "Bug Fix"
	SECURITY = "Security"
	ENHANCEMENT = "Enhancement"
	CHORE = "Chore"


class ChangeNote(PrDescription):
	change_type: ChangeType


class ReleasePrDesc(PrDescription):
	release_type: BumpType
	changes: dict[int, ChangeNote]


class ReleaseNoteBucket(msgspec.Struct):
	notes: dict[int, ChangeNote]


class DeferredReleasePlugin(CiBotPlugin):
	"""
	## Deferred Release Plugin
	This plugin is responsible for handling the deferred releases.
	### How to write a PR so CIBOT can understand it:
	1. add a tag to the PR for the type of change:
	    - [FEATURE] for new features
	    - [BUG FIX] for bug fixes
	    - [SECURITY] for security fixes
	    - [ENHANCEMENT] for enhancements
	    - [CHORE] for chores
	2. add description of the change in the first comment.
	It should look like so:
	```md
	This PR adds a new feature that allows users to do X.
	___
	Everything under this won't be added in the release notes.
	```
	3. When the project owner wants to initiate a release pipeline they should create a PR
	containing the Release tag of either [minor | major | patch] as a PR label.
	The author should also provide a description of the release in the PR description.
	i.e
	```md
	This release contains several bug fixes and a new feature that allows users to do X.
	___
	```
	"""

	supported_backednds: ClassVar[tuple[str, ...]] = ("github",)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._release_desc: ReleasePrDesc | None = None

	@override
	def plugin_name(self) -> str:
		return "Deferred Release"

	@override
	def on_pr_changed(self, pr) -> None:
		match note := self._parse_pr(pr):
			case ChangeNote():
				self._pr_comment = textwrap.dedent(
					f"""
                    ### {note.header}
                    Change Type: {note.change_type.value}
                    Description:  
                    {note.description}
                    """
				)
			case ReleasePrDesc():
				self._release_desc = note
				self._pr_comment = self._get_release_repr(note)

	@override
	def prepare_release(self, release_type: BumpType, next_version: str) -> list[Path]:
		changelog_file = Path.cwd() / "CHANGELOG.md"
		def update_change_log(current_changes: str, version: str) -> None:
			main_header = "CHANGELOG\n=========\n"

			this_header = textwrap.dedent(
				f"""{version} - {datetime.datetime.now(tz=datetime.UTC).date().isoformat()}\n--------------------\n""",
			)
			previous = changelog_file.read_text(encoding="utf-8").strip(main_header)
			changelog_file.write_text(
				textwrap.dedent(
					f"{main_header}{this_header}{current_changes}\n\n{previous}\n",
				),
				encoding="utf-8",
			)
		if self._release_desc:
			update_change_log(self._get_release_repr(self._release_desc, next_version), next_version)
			return [changelog_file]
		return []



	@override
	def on_commit_to_main(self, commit_hash: str) ->  None | ReleaseInfo:
		pr = self.backend.get_commit_associated_pr(commit_hash)
		bucket_key = f"{self.plugin_name()}-pending-changes"
		match res := self._parse_pr(pr.pr_number):
			case ChangeNote():
				if current_bucket := self.storage.get(bucket_key, ReleaseNoteBucket):
					current_bucket.notes[pr.pr_number] = res
				logger.info(f"Adding change note to pending changes: {res}")
				self.storage.set(
					bucket_key,
					current_bucket or ReleaseNoteBucket(notes={pr.pr_number: res}),
				)

			case ReleasePrDesc():
				return ReleaseInfo(note=self._get_release_repr(res))



	def _parse_pr(self, pr_id: int) -> ChangeNote | ReleasePrDesc | None:
		pr_description = self.backend.get_pr_description(pr_id)
		if release := self._get_release_desc_for_pr(pr_description):
			logger.info(f"prased pr as a release pr: {release}")
			return release

		labels = self.backend.get_pr_labels(pr_id)

		def find_change_type(label: str) -> ChangeType | None:
			for change_type in ChangeType:
				if change_type.value.lower() == label.lower():
					return change_type
			return None

		change_type = None

		for label in labels:
			if match := find_change_type(label):
				change_type = match
				break

		if change_type:
			ret = ChangeNote(
				change_type=change_type,
				header=pr_description.header,
				pr_number=pr_id,
				description=self._parse_pr_description(pr_description.description),
				contributor=pr_description.contributor,
			)
			logger.info(f"parsed pr as a change note: {ret}")
			return ret

		self._pr_comment = f"Couldn't parse PR\n {ERROR_GIF} \n {self.__doc__}"
		self._should_fail_work_flow = True

	def _get_release_desc_for_pr(self, pr_description: PrDescription) -> ReleasePrDesc | None:
		def find_release_type(label: str) -> BumpType | None:
			lower = label.lower()
			if "release" not in lower:
				return None
			for release_type in BumpType:
				if release_type.value.lower() in lower:
					return release_type
			return None

		labels = self.backend.get_pr_labels(pr_description.pr_number)
		release_type = None
		logger.info(f"searching for a release label in: {labels}")
		for label in labels:
			if match := find_release_type(label):
				release_type = match
				break
		if not release_type:
			logger.info("No release label found; this is not a release PR")
			return None

		logger.info(f"Found release label: {release_type}")
		logger.info("Checking for pending changes")
		if changes := self.storage.get(f"{self.plugin_name()}-pending-changes", ReleaseNoteBucket):
			logger.info(f"Found pending changes: {changes}")
			return ReleasePrDesc(
				contributor=pr_description.contributor,
				header=pr_description.header,
				description=self._parse_pr_description(pr_description.description),
				pr_number=pr_description.pr_number,
				release_type=release_type,
				changes=changes.notes,
			)

	def _get_release_repr(self, release: ReleasePrDesc, version: str | None = None) -> str:
		def repr_change_note_suffix(change_note: ChangeNote) -> str:
			settings = GithubSettings()
			return (
				f"Contributed by [{change_note.contributor.pr_author_fullname or change_note.contributor.pr_author_fullname}]"
				f"(https://github.com/{change_note.contributor.pr_author_fullname}) via [PR #{change_note.pr_number}]"
				f"(https://github.com/{settings.REPO_SLUG}/pull/{change_note.pr_number}/)"
			)

		changelogs_by_type: dict[ChangeType, list[ChangeNote]] = defaultdict(list)
		for change in release.changes.values():
			changelogs_by_type[change.change_type].append(change)

		comment = f"### Release: {version or release.release_type.value}\n"
		comment += "#### Changes\n"
		for change_type, changes in changelogs_by_type.items():
			comment += f"##### {change_type.value}(es)\n"
			for change in changes:
				comment += f"- **{change.header}** - {change.description}\n {repr_change_note_suffix(change)}\n"

		return comment

	def _parse_pr_description(self, pr_description: str) -> str:
		return pr_description.split("___")[0].strip()
