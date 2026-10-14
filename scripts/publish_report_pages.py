"""Publish the reviewed static archive using the user's existing GitHub credential."""
from pathlib import Path
import json
import subprocess
import httpx
from publish_github import credentials, OWNER, NAME

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "tmp/permanent-demo/site"


def main():
    assert (SITE / "index.html").exists() and (SITE / "archive/snapshot.json").exists()
    token, environment = credentials()
    with httpx.Client(base_url="https://api.github.com", headers={"Authorization":"Bearer " + token, "Accept":"application/vnd.github+json"}, timeout=45) as client:
        account = client.get("/user").raise_for_status().json()
        assert account["login"] == OWNER
        def git(*args):
            return subprocess.run(["git", *args], cwd=SITE, env=environment, check=True)
        if not (SITE / ".git").exists():
            assert client.get(f"/repos/{OWNER}/{NAME}/git/ref/heads/gh-pages").status_code == 404, "Existing pages branch needs review before updating."
            git("init", "-b", "gh-pages")
            git("config", "user.name", OWNER)
            git("config", "user.email", f"{account['id']}+{OWNER}@users.noreply.github.com")
            git("config", "core.autocrlf", "false")
            git("remote", "add", "origin", f"https://github.com/{OWNER}/{NAME}.git")
        git("add", ".")
        changes = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=SITE, env=environment)
        if changes.returncode:
            git("commit", "-m", "Deploy public real-report archive independent of serving laptop")
        git("push", "-u", "origin", "gh-pages")
        path = f"/repos/{OWNER}/{NAME}/pages"
        current = client.get(path)
        if current.status_code == 404:
            created = client.post(path, json={"source":{"branch":"gh-pages","path":"/"}})
            if created.status_code == 409 and created.json().get("message") == "GitHub Pages is already enabled.":
                page = client.get(path).raise_for_status().json()
            else:
                page = created.raise_for_status().json()
        else:
            page = current.raise_for_status().json()
            assert page["source"] == {"branch":"gh-pages","path":"/"}, "Do not replace an unrelated existing Pages site."
        result = dict(url=page["html_url"], host="GitHub Pages", free=True, laptop_required=False, new_inference=False, status=page["status"])
        (ROOT / "docs/submission/report-hosting.json").write_text(json.dumps(result, indent=2) + "\n")
        print("Published Pages branch; deployment requested:", result["url"], flush=True)


if __name__ == "__main__":
    main()
