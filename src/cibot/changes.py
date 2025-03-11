import datetime
import enum
import os
import subprocess
import textwrap
from dataclasses import dataclass
from typing import Protocol

import httpx
import toml as tomllib
from loguru import logger
from packaging.version import Version
from github.PullRequest import PullRequest

from . import githubref
from .utils import PATHS


PROJECT_NAME = "Backend"
git_username = "tzevet5Bot"
git_email = "bot@no.reply"


def git(*args: str) -> None:
    return subprocess.run(["git", *args], check=False).check_returncode()


def configure_git(username: str, email: str) -> None:
    git("config", "user.name", username)
    git("config", "user.email", email)


@dataclass
class PRContributor:
    pr_number: int
    pr_author_username: str
    pr_author_fullname: str | None

    def repr(self, repo_slug: str) -> str:
        return (
            f"Contributed by [{self.pr_author_fullname or self.pr_author_username}]"
            f"(https://github.com/{self.pr_author_username}) via [PR #{self.pr_number}]"
            f"(https://github.com/{repo_slug}/pull/{self.pr_number}/)"
        )


def get_first_comment(pr: PullRequest) -> tuple[str, PRContributor]:
    if comments := pr.get_issue_comments().get_page(0):
        return comments[0].body, PRContributor(
            pr_number=pr.number,
            pr_author_fullname=pr.user.name,
            pr_author_username=pr.user.login,
        )
    raise ValueError("No comments found in PR")


class ChangeType(enum.Enum):
    FEATURE = "Feature"
    BUG_FIX = "Bug Fix"
    SECURITY = "Security"
    ENHANCEMENT = "Enhancement"
    CHORE = "Chore"


@dataclass
class ChangeNote:
    change_type: ChangeType
    header: str
    description: str
    contributor: PRContributor


def parse_comment(pr: PullRequest) -> ChangeNote:
    """
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
    """
    labels = pr.get_labels()
    change_type = None
    for label in labels.get_page(0):
        for change_type in ChangeType:
            if change_type.value in label.name:
                change_type = change_type
    if change_type is None:
        raise ValueError("No change type found in PR labels")

    comment, contributor = get_first_comment(pr)
    header = pr.head.label
    description = comment.split("___")[0].strip()
    return ChangeNote(
        change_type=change_type,
        header=header,
        description=description,
        contributor=contributor,
    )


class ReleaseNoteStorage(Protocol):

	def append_change_notes(self, change_note: ChangeNote) -> ...:
		...


def append_change_notes(
	
) -> list[str]:
	return release_notes + [
		f"### {change_note.change_type.value}\n",
		f"- {change_note.header} - {change_note.description}\n",
		f"  {change_note.contributor.repr(githubref.REPO_SLUG)}\n",
	]