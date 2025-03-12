import os
from typing import ClassVar, override
from github.Repository import Repository


from cibot.backends.base import CiBotBackendBase, PRContributor, PrDescription
from cibot.storage_layers.base import BaseStorage


class GithubBackend(CiBotBackendBase):
    def __init__(self, repo: Repository, storage: BaseStorage) -> None:
        self.repo = repo
        self.changes_storage = storage

    BOT_COMMENT_ID: ClassVar[str] = "878ae1db-766f-49c7-a1a8-59f7be1fee8f"

    @override
    def name(self):
        return "github"

    @property
    def pr_number(self) -> int | None:
        if pr := os.environ.get("PR_NUMBER"):
            return int(pr)

    @override
    def create_pr_comment(self, content: str) -> None:
        if self.pr_number:
            self._create_or_update_bot_comment(
                self.pr_number,
                content,
                self.BOT_COMMENT_ID,
            )
        raise ValueError("PR_NUMBER not found in environment")

    @override
    def publish_release(self, project_name, version):
        raise NotImplementedError

    @override
    def get_pr_description(self, pr_number):
        pr = self.repo.get_pull(pr_number)
        return PrDescription(
            contributor=PRContributor(
                pr_number=pr_number,
                pr_author_username=pr.user.login,
                pr_author_fullname=pr.user.name,
            ),
            header=pr.title,
            description=pr.body,
            pr_number=pr_number,
        )

    @override
    def get_commit_associated_pr(self, commit_hash):
        return self.repo.get_commit(commit_hash).get_pulls()[0]

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
        comments = list(pr.get_issue_comments())

        for comment in reversed(comments):
            if identifier in comment.body:
                comment.edit(content)
                return
        # If no comment was found, create a new one
        pr.create_issue_comment(content)
