import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import quote

# Ensure project root on sys.path when running from scripts/
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aipart.services.github_api import GitHubAPI  # type: ignore


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), check=check, text=True, capture_output=True)


def ensure_git_available() -> None:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True, text=True)
    except Exception:
        print("[Error] 未检测到 Git，请先安装 Git 并确保在 PATH 中可用。", file=sys.stderr)
        raise


def git_config_get(root: Path, key: str) -> Optional[str]:
    try:
        cp = run(["git", "config", "--get", key], cwd=root)
        val = (cp.stdout or "").strip()
        return val or None
    except subprocess.CalledProcessError:
        return None


def git_config_set_local(root: Path, key: str, value: str) -> None:
    run(["git", "config", key, value], cwd=root)


def ensure_git_identity(root: Path, client: GitHubAPI) -> None:
    name = git_config_get(root, "user.name")
    email = git_config_get(root, "user.email")
    if not name or not email:
        login = None
        try:
            me = client.get_user()
            login = me.get("login")
        except Exception:
            pass
        if not name:
            name = login or os.environ.get("USERNAME") or os.environ.get("USER") or "Git User"
            git_config_set_local(root, "user.name", name)
        if not email:
            # 使用 noreply 邮箱，避免泄露真实地址
            email = "no-reply@users.noreply.github.com"
            git_config_set_local(root, "user.email", email)


def init_git_repo(root: Path, client: GitHubAPI) -> None:
    git_dir = root / ".git"
    if not git_dir.exists():
        run(["git", "init"], cwd=root)
    # 确保提交身份（避免首次提交失败）
    ensure_git_identity(root, client)
    # 确保主分支为 main
    try:
        run(["git", "rev-parse", "--verify", "main"], cwd=root)
    except subprocess.CalledProcessError:
        # 分支不存在时创建并切换
        run(["git", "checkout", "-B", "main"], cwd=root)
    # 添加文件并提交（允许空提交被跳过）
    run(["git", "add", "-A"], cwd=root)
    try:
        run(["git", "commit", "-m", "Initial commit"], cwd=root)
    except subprocess.CalledProcessError:
        # 可能没有变化
        pass


def set_remote(root: Path, name: str, url: str) -> None:
    # 存在则更新，不存在则添加
    try:
        run(["git", "remote", "add", name, url], cwd=root)
    except subprocess.CalledProcessError:
        run(["git", "remote", "set-url", name, url], cwd=root)


def push_with_token(root: Path, token: str, clone_url: str) -> None:
    # 将 https://github.com/owner/repo.git 转为 https://x-access-token:TOKEN@github.com/owner/repo.git
    if not clone_url.lower().startswith("https://"):
        raise RuntimeError("仅支持 HTTPS clone_url")
    # 安全编码 token，避免特殊字符影响 URL
    token_q = quote(token, safe="")
    push_url = clone_url.replace(
        "https://", f"https://x-access-token:{token_q}@", 1
    )
    # 使用 URL 直接 push，避免把 token 写入 remote config
    run(["git", "push", "-u", push_url, "main"], cwd=root)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="创建 GitHub 仓库并推送当前项目")
    parser.add_argument("--name", default=None, help="仓库名（默认使用目录名）")
    parser.add_argument("--org", default=None, help="组织名（可选）")
    vis = parser.add_mutually_exclusive_group()
    vis.add_argument("--private", dest="private", action="store_true", help="私有仓库（默认）")
    vis.add_argument("--public", dest="private", action="store_false", help="公开仓库")
    parser.set_defaults(private=True)
    parser.add_argument("--description", default="", help="仓库描述")
    parser.add_argument("--auto-init", action="store_true", help="GitHub 端自动初始化（README）")
    parser.add_argument("--remote-name", default="origin", help="远程名，默认 origin")
    parser.add_argument("--base-url", default="https://api.github.com", help="GitHub API 基础地址")
    args = parser.parse_args(argv)

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("[Error] 未检测到环境变量 GITHUB_TOKEN，请先设置它。", file=sys.stderr)
        return 1

    ensure_git_available()

    root = ROOT
    repo_name = args.name or root.name

    client = GitHubAPI(token=token, base_url=args.base_url)
    if not client.available:
        print("[Error] Token 不可用。", file=sys.stderr)
        return 1

    # 创建或复用远程仓库
    try:
        repo = client.create_repo(
            name=repo_name,
            private=args.private,
            description=args.description,
            auto_init=bool(args.auto_init),
            org=args.org,
        )
        created = True
    except Exception:
        # 可能是 422（仓库已存在），尝试推断 clone_url
        created = False
        try:
            me = client.get_user()
            owner = args.org or me.get("login")
            if not owner:
                raise RuntimeError("无法确定 owner")
            clone_url = f"https://github.com/{owner}/{repo_name}.git"
            html_url = f"https://github.com/{owner}/{repo_name}"
            repo = {"clone_url": clone_url, "html_url": html_url, "full_name": f"{owner}/{repo_name}"}
        except Exception as inner:
            print(f"[Error] 创建仓库失败且无法推断现有仓库: {inner}", file=sys.stderr)
            return 2

    clone_url = repo.get("clone_url")
    html_url = repo.get("html_url")

    # 初始化并推送
    init_git_repo(root, client)
    # 永远把 remote 设置成不含 token 的 URL
    set_remote(root, args.remote_name, clone_url)

    try:
        push_with_token(root, token, clone_url)
    except subprocess.CalledProcessError as e:
        # 输出精简的错误信息（不泄露 token）
        print("[Error] git push 失败：\n" + (e.stderr or e.stdout or str(e)), file=sys.stderr)
        return 3

    print(("已创建并推送到: " if created else "已复用并推送到: ") + html_url)
    print("远程名:", args.remote_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
