"""Publish this local repository and sync stable-title planning items using gh."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def run(args, check=True):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)


def gh_json(*args):
    return json.loads(run(["gh", *args]).stdout)


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", sys.argv[1]):
        raise SystemExit("Usage: python3 scripts/publish_github.py OWNER/REPOSITORY")
    repo = sys.argv[1]
    run(["gh", "auth", "status", "-h", "github.com"])
    run(["git", "rev-parse", "--verify", "HEAD"])
    if run(["git", "status", "--porcelain"]).stdout.strip():
        raise SystemExit("Commit local changes before publishing.")
    url = "https://github.com/" + repo + ".git"
    remote = run(["git", "remote", "get-url", "origin"], check=False)
    acceptable = {url, url[:-4], "git@github.com:" + repo + ".git"}
    if remote.returncode == 0 and remote.stdout.strip() not in acceptable:
        raise SystemExit("Origin points elsewhere. Refusing to replace it.")
    lookup = run(["gh", "repo", "view", repo, "--json", "nameWithOwner"], check=False)
    if lookup.returncode != 0:
        run(["gh", "repo", "create", repo, "--private", "--description",
             "Readable race intelligence: simulated telemetry to race state and web UI"])
    if remote.returncode != 0:
        if run(["git", "ls-remote", url]).stdout.strip():
            raise SystemExit("Existing repository is not empty. Refusing to push into it.")
        run(["git", "remote", "add", "origin", url])
    run(["git", "push", "-u", "origin", "main"])
    plan = json.loads((ROOT / "docs/github-plan.json").read_text())
    milestones = gh_json("api", "--paginate", "--slurp", "repos/" + repo + "/milestones?state=all&per_page=100")
    milestone_by_title = {item["title"]: item["number"] for page in milestones for item in page}
    issues = gh_json("api", "--paginate", "--slurp", "repos/" + repo + "/issues?state=all&per_page=100")
    existing_titles = {item["title"] for page in issues for item in page if "pull_request" not in item}
    for milestone in plan:
        title = milestone["title"]
        if title not in milestone_by_title:
            created = gh_json("api", "--method", "POST", "repos/" + repo + "/milestones",
                              "-f", "title=" + title, "-f", "description=" + milestone["description"])
            milestone_by_title[title] = created["number"]
        for issue in milestone["issues"]:
            if issue["title"] in existing_titles:
                continue
            gh_json("api", "--method", "POST", "repos/" + repo + "/issues",
                    "-f", "title=" + issue["title"], "-f", "body=" + issue["body"],
                    "-F", "milestone=" + str(milestone_by_title[title]))
            existing_titles.add(issue["title"])
    print("Repository and planning items ready: https://github.com/" + repo)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr.strip() or "Command failed; inspect GitHub login and repository permissions.")
