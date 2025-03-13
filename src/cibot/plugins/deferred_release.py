import enum
import textwrap
from typing import ClassVar, override

import msgspec
from cibot.backends.base import ERROR_GIF, PrDescription
from cibot.plugins.base import CiBotPlugin, ReleaseType


class ChangeType(enum.Enum):
    FEATURE = "Feature"
    BUG_FIX = "Bug Fix"
    SECURITY = "Security"
    ENHANCEMENT = "Enhancement"
    CHORE = "Chore"


class ChangeNote(PrDescription):
    change_type: ChangeType


class ReleasePr(PrDescription):
    release_type: ReleaseType


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
    containing the Release tag of either [minor | major | patch]:
    ```md
    This PR initiates the release pipeline.
    ___

    """

    supported_backednds: ClassVar[tuple[str, ...]] = ("github",)

    @override
    def plugin_name(self) -> str:
        return "Deferred Release"

    @override
    def on_pr_changed(self, pr) -> None:
        match note := self._get_change_notes_for_current_pr(pr):
            case ChangeNote():
                self._pr_comment = textwrap.dedent(
                    f"""
                    ### {note.header}
                    Change Type: {note.change_type.value}
                    Description:  
                    {note.description}
                    """
                )
            case ReleasePr():
                self._pr_comment = textwrap.dedent(
                    f"""
                    ### Release: {note.release_type.value}
                    """
                )

    @override
    def provide_comment_for_pr(self):
        return self._pr_comment

    @override
    def on_commit_to_main(self, commit_hash: str):
        pr = self.backend.get_commit_associated_pr(commit_hash)
        bucket_key = f"{self.plugin_name()}-pending-changes"
        match note := self._get_change_notes_for_current_pr(pr.pr_number):
            case ChangeNote():
                if current_bucket := self.storage.get(bucket_key, ReleaseNoteBucket):
                    current_bucket.notes[pr.pr_number] = note
                self.storage.set(bucket_key, current_bucket or ReleaseNoteBucket(notes={pr.pr_number: note}))

            case ReleasePr():
                self._pr_comment = textwrap.dedent(
                    f"""
                    ### Release: {note.release_type.value}
                    """
                )

    # def repr_change_note(self, repo: Repository, change_note: ChangeNote) -> str:
    #     return (
    #         f"Contributed by [{change_note.contributor.pr_author_fullname or change_note.contributor.pr_author_fullname}]"
    #         f"(https://github.com/{change_note.contributor.pr_author_fullname}) via [PR #{change_note.pr_number}]"
    #         f"(https://github.com/{repo_slug}/pull/{change_note.pr_number}/)"
    #     )

    def _get_change_notes_for_current_pr(self, pr_id: int) -> ChangeNote | ReleasePr | None:
        labels = self.backend.get_pr_labels(pr_id)


        def find_change_type(label: str) -> ChangeType | None:
            for change_type in ChangeType:
                if change_type.value.lower() == label.lower():
                    return change_type
            return None
        
        def find_release_type(label: str) -> ReleaseType | None:
            lower = label.lower()
            if 'release' not in lower:
                return None

            for release_type in ReleaseType:
                if release_type.value.lower() in lower:
                    return release_type
            return None
        change_type = None
        release_type = None
        
        for label in labels:
            if match := find_change_type(label):
                change_type = match
                break
            if match := find_release_type(label):
                release_type = match
                break


        def parse_pr_description(pr_description: str) -> str:
            return pr_description.split("___")[0].strip()

        pr_description = self.backend.get_pr_description(pr_id)
        if release_type:
            return ReleasePr(
                header=pr_description.header,
                pr_number=pr_id,
                description=parse_pr_description(pr_description.description),
                contributor=pr_description.contributor,
                release_type=release_type,
            )
        if change_type:
            return ChangeNote(
                change_type=change_type,
                header=pr_description.header,
                pr_number=pr_id,
                description=parse_pr_description(pr_description.description),
                contributor=pr_description.contributor,
            )
        self._pr_comment = (
            f"No change type found in the PR labels\n {ERROR_GIF} \n {self.__doc__}"
        )
        self._should_fail_work_flow = True