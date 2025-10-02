import os
import sys
import json
import argparse
from typing import Optional, Dict, Any, List

# 确保可从脚本直接运行（将项目根目录加入 sys.path）
try:
    from aipart.services.github_api import GitHubAPI
except ModuleNotFoundError:
    _here = os.path.dirname(__file__)
    _root = os.path.dirname(_here)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from aipart.services.github_api import GitHubAPI


def build_client(token: Optional[str], base_url: str) -> GitHubAPI:
    return GitHubAPI(token=token, base_url=base_url)


def cmd_list_repos(args: argparse.Namespace) -> int:
    client = build_client(args.token, args.base_url)
    try:
        repos = client.list_repos(per_page=args.per_page)
    except RuntimeError as e:
        print(f"[Error] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[Error] 调用 GitHub API 失败: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(repos, ensure_ascii=False, indent=2))
    else:
        for r in repos:
            full = r.get("full_name") or f"{r.get('owner',{}).get('login','?')}/{r.get('name','?')}"
            vis = "private" if r.get("private") else "public"
            print(f"- {full} ({vis}) ⭐{r.get('stargazers_count',0)}")
    return 0


def cmd_create_issue(args: argparse.Namespace) -> int:
    client = build_client(args.token, args.base_url)
    labels: Optional[List[str]] = None
    if args.labels:
        labels = [s.strip() for s in args.labels.split(',') if s.strip()]
    try:
        issue = client.create_issue(args.owner, args.repo, args.title, body=args.body or "", labels=labels)
    except RuntimeError as e:
        print(f"[Error] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[Error] 创建 issue 失败: {e}", file=sys.stderr)
        return 2

    url = issue.get("html_url") or issue.get("url")
    num = issue.get("number")
    print(f"已创建 Issue #{num}: {url}")
    return 0


def cmd_dispatch_workflow(args: argparse.Namespace) -> int:
    client = build_client(args.token, args.base_url)
    inputs: Optional[Dict[str, Any]] = None
    if args.inputs:
        try:
            inputs = json.loads(args.inputs)
            if not isinstance(inputs, dict):
                raise ValueError("inputs 必须是 JSON 对象")
        except Exception as e:
            print(f"[Error] 解析 --inputs 失败: {e}", file=sys.stderr)
            return 3

    try:
        ok = client.dispatch_workflow(args.owner, args.repo, args.workflow, ref=args.ref, inputs=inputs)
    except RuntimeError as e:
        print(f"[Error] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[Error] 触发 workflow 失败: {e}", file=sys.stderr)
        return 2

    print("已触发 workflow_dispatch: {} @ {} (.github/workflows/{})".format(args.repo, args.ref, args.workflow))
    return 0


def cmd_create_repo(args: argparse.Namespace) -> int:
    client = build_client(args.token, args.base_url)
    try:
        repo = client.create_repo(
            name=args.name,
            private=args.private,
            description=args.description or "",
            auto_init=bool(args.auto_init),
            org=args.org,
        )
    except RuntimeError as e:
        print(f"[Error] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[Error] 创建仓库失败: {e}", file=sys.stderr)
        return 2

    if getattr(args, "json", False):
        print(json.dumps(repo, ensure_ascii=False))
        return 0

    full = repo.get("full_name")
    html_url = repo.get("html_url")
    clone_https = repo.get("clone_url")
    visibility = "private" if repo.get("private") else "public"
    print(f"已创建仓库 {full} ({visibility})")
    print(f"Web: {html_url}")
    print(f"Clone (HTTPS): {clone_https}")
    return 0


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GitHub API 命令行工具")
    p.add_argument("--token", default=os.getenv("GITHUB_TOKEN"), help="GitHub Token（缺省读取环境变量 GITHUB_TOKEN）")
    p.add_argument("--base-url", default="https://api.github.com", help="API 基础地址（GitHub Enterprise 可改）")

    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("list-repos", help="列出当前用户仓库")
    sp.add_argument("--per-page", type=int, default=5, help="每页数量，默认 5")
    sp.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    sp.set_defaults(func=cmd_list_repos)

    sp = sub.add_parser("create-issue", help="在指定仓库创建 Issue")
    sp.add_argument("owner", help="仓库 owner（用户或组织名）")
    sp.add_argument("repo", help="仓库名")
    sp.add_argument("title", help="Issue 标题")
    sp.add_argument("--body", default="", help="Issue 内容")
    sp.add_argument("--labels", default="", help="标签，英文逗号分隔，如 bug,help wanted")
    sp.set_defaults(func=cmd_create_issue)

    sp = sub.add_parser("dispatch-workflow", help="触发工作流 .github/workflows/<file>.yml 的 workflow_dispatch 事件")
    sp.add_argument("owner", help="仓库 owner")
    sp.add_argument("repo", help="仓库名")
    sp.add_argument("workflow", help="工作流文件名，如 ci.yml 或 release.yml")
    sp.add_argument("--ref", default="main", help="分支或 tag，默认 main")
    sp.add_argument("--inputs", default=None, help="JSON 字符串，传递给 workflow inputs")
    sp.set_defaults(func=cmd_dispatch_workflow)

    sp = sub.add_parser("create-repo", help="创建仓库（默认创建到当前用户名下）")
    sp.add_argument("name", help="仓库名称")
    sp.add_argument("--org", default=None, help="组织名（在该组织下创建）")
    vis = sp.add_mutually_exclusive_group()
    vis.add_argument("--private", dest="private", action="store_true", help="创建为私有仓库（默认）")
    vis.add_argument("--public", dest="private", action="store_false", help="创建为公开仓库")
    sp.set_defaults(private=True)
    sp.add_argument("--description", default="", help="仓库描述")
    sp.add_argument("--auto-init", action="store_true", help="GitHub 端自动初始化（README）")
    sp.add_argument("--json", action="store_true", help="以 JSON 格式输出创建结果")
    sp.set_defaults(func=cmd_create_repo)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if not args.token:
        print("[Error] 缺少 Token。请通过 --token 传入或设置环境变量 GITHUB_TOKEN。", file=sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
