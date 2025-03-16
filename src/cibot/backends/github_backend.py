from typing import ClassVar, override

import github
import github.PullRequest
from github.Repository import Repository

from cibot.backends.base import CiBotBackendBase, PRContributor, PrDescription
from cibot.storage_layers.base import BaseStorage


class GithubBackend(CiBotBackendBase):
	def __init__(self, repo: Repository, storage: BaseStorage, pr_number: int | None) -> None:
		self.repo = repo
		self.changes_storage = storage
		self.pr_number = pr_number

	BOT_COMMENT_ID: ClassVar[str] = "878ae1db-766f-49c7-a1a8-59f7be1fee8f"

	@override
	def name(self):
		return "github"

	@override
	def create_pr_comment(self, content: str) -> None:
		if not self.pr_number:
			raise ValueError("pr_number is not set")

		self._create_or_update_bot_comment(
			self.pr_number,
			content,
			self.BOT_COMMENT_ID,
		)

	@override
	def publish_release(self, project_name, version):
		raise NotImplementedError

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

	def _create_or_update_bot_comment(
		self,
		pr_number: int,
		content: str,
		identifier: str,
	) -> None:
		pr = self.repo.get_pull(pr_number)

		for comment in pr.get_issue_comments():
			if identifier in comment.body:
				comment.delete()
				break
		content += f"\n<!--CIBOT-COMMENT-ID {identifier} -->"
		# If no comment was found, create a new one
		pr.create_issue_comment(content)
