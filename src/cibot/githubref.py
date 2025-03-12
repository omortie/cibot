from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository


def get_github_session(token: str) -> Github:
    return Github(token)


def get_repo(g: Github, repo_slug: str) -> Repository:
    return g.get_repo(repo_slug)


def get_pr(g: Github, repo_slug: str, num: int) -> PullRequest:
    return get_repo(g, repo_slug).get_pull(num)
