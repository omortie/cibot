import datetime
import os
import subprocess
import textwrap
from dataclasses import dataclass

import httpx
import toml as tomllib
from loguru import logger
from packaging.version import Version

from . import githubref
from .releasefile import ReleasePreview, parse_release_file
from .utils import PATHS


git_username = "cibot"
git_email = "bot@no.reply"


def git(*args: str) -> None:
	return subprocess.run(["git", *args], check=False).check_returncode()


def configure_git(username: str, email: str) -> None:
	git("config", "user.name", username)
	git("config", "user.email", email)


def get_current_version() -> str:
	pyproject = tomllib.loads(PATHS.PYPROJECT_TOML.read_text(encoding="utf-8"))
	return pyproject["project"]["version"]


def bump_version(bump_string: str) -> None:
	current_version = Version(get_current_version())

	def semver_to_str(major: int, minor: int, patch: int) -> str:
		return f"{major}.{minor}.{patch}"

	match bump_string.lower():
		case "major":
			new_version = semver_to_str(current_version.major + 1, 0, 0)
		case "minor":
			new_version = semver_to_str(current_version.major, current_version.minor + 1, 0)
		case "patch":
			new_version = semver_to_str(
				current_version.major, current_version.minor, current_version.micro + 1
			)
		case _:
			msg = f"Unknown bump string: {bump_string}"
			raise ValueError(msg)
	pyproject = tomllib.loads(PATHS.PYPROJECT_TOML.read_text(encoding="utf-8"))
	pyproject["project"]["version"] = new_version
	PATHS.PYPROJECT_TOML.write_text(tomllib.dumps(pyproject), encoding="utf-8")


def pprint_release_change_log(release_preview: ReleasePreview, contrib_details: str) -> str:
	current_changes = release_preview.changelog_no_header

	def is_first_or_last_line_empty(s: str) -> bool:
		return s.startswith("\n") or s.endswith("\n")

	while is_first_or_last_line_empty(current_changes):
		current_changes = current_changes.strip("\n")
	return f"{current_changes}\n\n{contrib_details}"


def update_change_log(current_changes: str, version: str) -> None:
	main_header = "CHANGELOG\n=========\n"

	this_header = textwrap.dedent(
		f"""{version} - {datetime.datetime.now(tz=datetime.UTC).date().isoformat()}\n--------------------\n""",
	)
	previous = PATHS.CHANGELOG.read_text(encoding="utf-8").strip(main_header)
	PATHS.CHANGELOG.write_text(
		textwrap.dedent(
			f"{main_header}{this_header}{current_changes}\n\n{previous}\n",
		),
		encoding="utf-8",
	)


def main() -> None:
	os.chdir(PATHS.PROJECT_ROOT)
	release_file = parse_release_file(PATHS.RELEASE_FILE.read_text(encoding="utf-8"))
	bump_version(release_file.type.value)
	bumped_version = get_current_version()
	token = os.getenv("BOT_TOKEN")
	assert token
	current_contributor = get_last_commit_contributor(token=token)
	contributor_details = get_contributor_details(current_contributor)
	pretty_changes = pprint_release_change_log(release_file, contributor_details)
	update_change_log(pretty_changes, bumped_version)
	configure_git(git_username, git_email)

	git(
		"add",
		str(PATHS.PYPROJECT_TOML.resolve(True)),  # noqa: FBT003
		str(PATHS.CHANGELOG.resolve(True)),  # noqa: FBT003
	)
	# remove release file
	git("rm", str(PATHS.RELEASE_FILE))
	git("commit", "-m", f"Release {PROJECT_NAME}@{bumped_version}", "--no-verify")
	git("push", "origin", "HEAD")
	# GitHub release
	repo = githubref.get_repo(githubref.get_github_session(os.getenv("BOT_TOKEN", "")))
	release = repo.create_git_release(
		name=f"{PROJECT_NAME} {bumped_version}",
		tag=bumped_version,
		generate_release_notes=False,
		message=pretty_changes,
	)
	logger.info(f"Release created: {release.html_url}")


if __name__ == "__main__":
	main()
