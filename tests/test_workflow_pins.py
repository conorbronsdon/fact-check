"""GitHub Actions hardening: SHA pins, top-level permissions, Dependabot."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GH = ROOT / ".github"
USES = re.compile(r"""^\s*(?:-\s+)?uses:\s*["']?([^\s"'#]+)""")
FULL_SHA = re.compile(r"@[0-9a-f]{40}$")


def unpinned_uses(text):
    bad = []
    for line in text.replace("\r\n", "\n").split("\n"):
        m = USES.match(line)
        if not m:
            continue
        ref = m.group(1)
        if ref.startswith("./") or ref.startswith("docker://"):
            continue
        if not FULL_SHA.search(ref):
            bad.append(ref)
    return bad


def workflow_files():
    files = [p for p in (GH / "workflows").glob("*") if p.suffix in (".yml", ".yaml")]
    if (GH / "actions").is_dir():
        files += [p for p in (GH / "actions").rglob("*") if p.suffix in (".yml", ".yaml")]
    return sorted(files)


class Parser(unittest.TestCase):
    def test_flags_tag_short_sha_and_branch(self):
        self.assertEqual(unpinned_uses("      - uses: actions/checkout@v4\n"),
                         ["actions/checkout@v4"])
        self.assertEqual(unpinned_uses("      - uses: actions/checkout@11d5960\n"),
                         ["actions/checkout@11d5960"])
        self.assertEqual(unpinned_uses("        uses: actions/setup-python@main\n"),
                         ["actions/setup-python@main"])

    def test_accepts_full_sha_and_local_actions(self):
        text = (
            "      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0\n"
            "      - uses: ./.github/actions/local\n"
            "      - uses: docker://alpine:3.20\n"
        )
        self.assertEqual(unpinned_uses(text), [])


class Workflows(unittest.TestCase):
    def test_workflows_exist(self):
        self.assertTrue(workflow_files())

    def test_every_uses_is_sha_pinned(self):
        for path in workflow_files():
            with self.subTest(path=path.name):
                self.assertEqual(unpinned_uses(path.read_text(encoding="utf-8")), [])

    def test_every_workflow_sets_top_level_permissions(self):
        for path in (GH / "workflows").glob("*.y*ml"):
            with self.subTest(path=path.name):
                self.assertRegex(path.read_text(encoding="utf-8"), re.compile(r"^permissions:", re.M))

    def test_dependabot_watches_github_actions(self):
        text = (GH / "dependabot.yml").read_text(encoding="utf-8")
        self.assertRegex(text, r"package-ecosystem:\s*[\"']?github-actions\b")


if __name__ == "__main__":
    unittest.main()
