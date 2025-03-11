from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository


def get_github_session(token: str) -> Github:
    return Github(token)


def get_repo(g: Github, repo_slug: str) -> Repository:
    return g.get_repo(repo_slug)


def get_pr(g: Github,  repo_slug: str, num: int) -> PullRequest:
    return get_repo(g, repo_slug).get_pull(num)


def create_or_update_bot_comment(
    pr: PullRequest,
    content: str,
    identifier: str,
) -> None:
    comments = list(pr.get_issue_comments())

    for comment in reversed(comments):
        if identifier in comment.body:
            comment.edit(content)
            return

    pr.create_issue_comment(content)
