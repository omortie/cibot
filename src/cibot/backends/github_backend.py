from functools import cached_property
from typing import ClassVar, override

import github
import github.PullRequest
from github.Repository import Repository
from loguru import logger
from pydantic_settings import BaseSettings

from cibot.backends.base import (
	CiBotBackendBase,
	PRContributor,
	PrDescription,
	PrReviewComment,
	ReleaseInfo,
)
from cibot.storage_layers.base import BaseStorage


class GithubSettings(BaseSettings):
	model_config = {
		"env_prefix": "CIBOT_GITHUB_",
	}
	TOKEN: str | None = None
	REPO_SLUG: str | None = None


class GithubBackend(CiBotBackendBase):
	def __init__(
		self,
		repo: Repository,
		storage: BaseStorage,
		pr_number: int | None,
		settings: GithubSettings,
	) -> None:
		self.repo = repo
		self.changes_storage = storage
		self.pr_number = pr_number
		self.settings = settings

	BOT_COMMENT_ID: ClassVar[str] = "878ae1db-766f-49c7-a1a8-59f7be1fee8f"

	@override
	def name(self):
		return "github"

	@override
	def configure_git(self) -> None:
		self.git("config", "user.name", "cibot")
		self.git("config", "user.email", "cibot@no.reply")

	@override
	def upsert_pr_comment(self, content: str, comment_id: str) -> None:
		pr = self._pr

		for comment in pr.get_issue_comments().reversed:
			if comment_id in comment.body:
				comment.delete()
				break
		content += f"\n<!--CIBOT-COMMENT-ID {comment_id} -->"
		# If no comment was found, create a new one
		pr.create_issue_comment(content)

	@override
	def create_pr_review_comment(self, comment: PrReviewComment) -> None:
		latest_commit = self._pr.get_commits().reversed[0]
		content = f"""
[//]: {comment.content_id}
{comment.content}
"""
		start, end = comment.start_line, comment.end_line
		if start:
			self._pr.create_review_comment(
				body=content, path=comment.file, start_line=start, line=end, commit=latest_commit
			)
		else:
			self._pr.create_review_comment(
				body=content, path=comment.file, line=end, commit=latest_commit
			)

	@override
	def get_review_comments_for_content_id(self, id: str) -> list[tuple[int, PrReviewComment]]:
		review_comments = self._pr.get_review_comments()
		ret = []
		for comment in review_comments:
			if id in comment.body:
				pr_comment = PrReviewComment(
					content_id=id,
					file=comment.path,
					start_line=comment.start_line,
					end_line=comment.line,
					content=comment.body,
					pr_number=self._pr.number,
				)
				ret.append((comment.id, pr_comment))
		return ret

	@override
	def delete_pr_review_comment(self, comment_id: int) -> None:
		self._pr.get_review_comment(comment_id).delete()

	@override
	def publish_release(self, release_info: ReleaseInfo):
		release = self.repo.create_git_release(
			name=release_info.header,
			tag=release_info.version,
			generate_release_notes=False,
			message=release_info.note,
		)
		logger.info(f"Published release {release_info.version} at {release.html_url}")

	@override
	def get_pr_description(self, pr_number):
		pr = self.repo.get_pull(pr_number)
		return self._pr_desc_from_pr(pr)

	def _pr_desc_from_pr(self, pr: github.PullRequest.PullRequest) -> PrDescription:
		return PrDescription(
			contributor=PRContributor(
				pr_number=pr.number,
				pr_author_username=pr.user.login,
				pr_author_fullname=pr.user.name,
			),
			header=pr.title,
			description=pr.body,
			pr_number=pr.number,
		)

	@override
	def get_commit_associated_pr(self, commit_hash) -> PrDescription:
		return self._pr_desc_from_pr(self.repo.get_commit(commit_hash).get_pulls()[0])

	@override
	def get_pr_labels(self, pr_number):
		return [label.name for label in self.repo.get_pull(pr_number).labels]

	@cached_property
	def _pr(self) -> github.PullRequest.PullRequest:
		assert self.pr_number is not None, "pr_number is not set"
		return self.repo.get_pull(self.pr_number)
