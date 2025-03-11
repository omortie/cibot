import datetime
import os
import subprocess
import textwrap
from dataclasses import dataclass

import httpx
import toml as tomllib
from loguru import logger
from packaging.version import Version
from github.PullRequest import PullRequest

from . import githubref
from .releasefile import ReleasePreview, parse_release_file
from .utils import PATHS

REPO_SLUG = "tzevet5/Backend"

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


def get_contributor_details(conributor: PRContributor) -> str:
