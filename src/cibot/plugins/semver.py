import re
from pathlib import Path
from typing import override

from packaging.version import Version

from cibot.plugins.base import BumpType, VersionBumpPlugin

SEMVER_REGEX = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def bumped_version(bump_type: BumpType, version_raw: str) -> str:
	current_version = Version(version_raw)

	def semver_to_str(major: int, minor: int, patch: int) -> str:
		return f"{major}.{minor}.{patch}"

	match bump_type:
		case BumpType.MAJOR:
			new_version = semver_to_str(current_version.major + 1, 0, 0)
		case BumpType.MINOR:
			new_version = semver_to_str(current_version.major, current_version.minor + 1, 0)
		case BumpType.PATCH:
			new_version = semver_to_str(
				current_version.major, current_version.minor, current_version.micro + 1
			)
		case _:
			raise ValueError(f"Invalid bump type: {bump_type}")
	return new_version


class SemverPlugin(VersionBumpPlugin):
	
	supported_backednds = ("*",)
	@override
	def plugin_name(self) -> str:
		return "semver"

	@override
	def next_version(self, bump_type: BumpType) -> str:
		current_version = self._current_version_from_pyproject()
		new_version = bumped_version(bump_type, current_version)
		self._pr_comment = f"Bumping version to {new_version}. Bump type: {bump_type}."
		return new_version

	@override
	def prepare_release(self, release_type: BumpType, next_version: str) -> list[Path]:
		self._bump_pyproject(next_version)
		return [self._pyproject]

	@property
	def _pyproject(self) -> Path:
		return Path.cwd() / "pyproject.toml"

	def _bump_pyproject(self, new_version: str) -> None:
		content = self._pyproject.read_text()
		new_content = re.sub(SEMVER_REGEX, new_version, content)
		self._pyproject.write_text(new_content)

	def _current_version_from_pyproject(self) -> str:
		content = self._pyproject.read_text()
		for line in content.split("\n"):
			version_match = SEMVER_REGEX.match(line)
			if version_match:
				return version_match.group(0)
		raise ValueError("Invalid version format in pyproject.toml")
