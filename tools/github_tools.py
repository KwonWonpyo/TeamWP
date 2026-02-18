"""
tools/github_tools.py

에이전트들이 GitHub 저장소와 상호작용하기 위한 커스텀 툴 모음
"""

from __future__ import annotations

import os
from typing import List, Optional
from github import Github
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# 공통 GitHub 클라이언트
# ─────────────────────────────────────────────
def get_github_client():
    token = os.getenv("GITHUB_TOKEN")
    repo_name = os.getenv("GITHUB_REPO")
    g = Github(token)
    return g.get_repo(repo_name)


# ─────────────────────────────────────────────
# 이슈 목록 조회
# ─────────────────────────────────────────────
class ListIssuesInput(BaseModel):
    state: str = Field(default="open", description="이슈 상태: 'open' | 'closed' | 'all'")
    label: str = Field(default="", description="필터링할 라벨명 (빈 문자열이면 전체)")


class ListIssuesTool(BaseTool):
    name: str = "list_github_issues"
    description: str = "GitHub 저장소의 이슈 목록을 조회합니다."
    args_schema: type[BaseModel] = ListIssuesInput

    def _run(self, state: str = "open", label: str = "") -> str:
        repo = get_github_client()
        kwargs = {"state": state}
        if label:
            kwargs["labels"] = [label]

        issues = repo.get_issues(**kwargs)
        result = []
        for issue in issues[:10]:  # 최대 10개
            result.append(f"[#{issue.number}] {issue.title} | {issue.state} | {issue.html_url}")

        return "\n".join(result) if result else "이슈가 없습니다."


# ─────────────────────────────────────────────
# 이슈 상세 조회
# ─────────────────────────────────────────────
class GetIssueInput(BaseModel):
    issue_number: int = Field(description="조회할 이슈 번호")


class GetIssueTool(BaseTool):
    name: str = "get_github_issue"
    description: str = "특정 GitHub 이슈의 상세 내용을 가져옵니다."
    args_schema: type[BaseModel] = GetIssueInput

    def _run(self, issue_number: int) -> str:
        repo = get_github_client()
        issue = repo.get_issue(issue_number)
        comments = []
        for c in issue.get_comments():
            author = getattr(getattr(c, "user", None), "login", "unknown")
            comments.append(f"[{author}] {c.body}")

        return f"""
이슈 #{issue.number}: {issue.title}
상태: {issue.state}
작성자: {issue.user.login}
라벨: {[l.name for l in issue.labels]}

본문:
{issue.body}

댓글 ({len(comments)}개):
{chr(10).join(f'- {c}' for c in comments)}
"""


# ─────────────────────────────────────────────
# 브랜치 생성
# ─────────────────────────────────────────────
class CreateBranchInput(BaseModel):
    new_branch: str = Field(description="생성할 브랜치명 (예: feature/issue-42)")
    base_branch: str = Field(default="main", description="기준 브랜치명")


class CreateBranchTool(BaseTool):
    name: str = "create_github_branch"
    description: str = "기준 브랜치에서 새 브랜치를 생성합니다. 이미 있으면 그대로 사용합니다."
    args_schema: type[BaseModel] = CreateBranchInput

    def _run(self, new_branch: str, base_branch: str = "main") -> str:
        repo = get_github_client()
        try:
            repo.get_branch(new_branch)
            return f"브랜치가 이미 존재합니다: {new_branch}"
        except Exception:
            pass

        base = repo.get_branch(base_branch)
        repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=base.commit.sha)
        return f"브랜치 생성 완료: {new_branch} (base: {base_branch})"


# ─────────────────────────────────────────────
# 이슈에 댓글 추가
# ─────────────────────────────────────────────
class CommentIssueInput(BaseModel):
    issue_number: int = Field(description="댓글을 달 이슈 번호")
    comment: str = Field(description="댓글 내용")


class CommentIssueTool(BaseTool):
    name: str = "comment_github_issue"
    description: str = "GitHub 이슈에 댓글을 추가합니다."
    args_schema: type[BaseModel] = CommentIssueInput

    def _run(self, issue_number: int, comment: str) -> str:
        repo = get_github_client()
        issue = repo.get_issue(issue_number)
        issue.create_comment(comment)
        return f"이슈 #{issue_number}에 댓글이 추가되었습니다."


# ─────────────────────────────────────────────
# 파일 내용 읽기
# ─────────────────────────────────────────────
class ReadFileInput(BaseModel):
    file_path: str = Field(description="읽을 파일 경로 (예: src/components/Login.tsx)")
    branch: str = Field(default="main", description="브랜치명")


class ReadFileTool(BaseTool):
    name: str = "read_github_file"
    description: str = "GitHub 저장소의 특정 파일 내용을 읽습니다."
    args_schema: type[BaseModel] = ReadFileInput

    def _run(self, file_path: str, branch: str = "main") -> str:
        repo = get_github_client()
        try:
            content = repo.get_contents(file_path, ref=branch)
            return content.decoded_content.decode("utf-8")
        except Exception as e:
            return f"파일을 찾을 수 없습니다: {file_path} ({e})"


# ─────────────────────────────────────────────
# 파일 생성/수정 후 커밋
# ─────────────────────────────────────────────
class WriteFileInput(BaseModel):
    file_path: str = Field(description="생성/수정할 파일 경로")
    content: str = Field(description="파일 전체 내용")
    commit_message: str = Field(description="커밋 메시지")
    branch: str = Field(default="main", description="브랜치명")


class WriteFileTool(BaseTool):
    name: str = "write_github_file"
    description: str = "GitHub 저장소에 파일을 생성하거나 수정하고 커밋합니다."
    args_schema: type[BaseModel] = WriteFileInput

    def _run(self, file_path: str, content: str, commit_message: str, branch: str = "main") -> str:
        repo = get_github_client()
        try:
            # 파일이 이미 존재하면 업데이트
            existing = repo.get_contents(file_path, ref=branch)
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=existing.sha,
                branch=branch,
            )
            return f"파일 수정 완료: {file_path} (브랜치: {branch})"
        except Exception:
            # 없으면 새로 생성
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch,
            )
            return f"파일 생성 완료: {file_path} (브랜치: {branch})"


# ─────────────────────────────────────────────
# 이슈 생성 (후속 작업용 — agent-followup 라벨 사용, agent-todo 사용 금지)
# ─────────────────────────────────────────────
class CreateIssueInput(BaseModel):
    title: str = Field(description="이슈 제목")
    body: str = Field(description="이슈 본문 (마크다운 가능)")
    labels: List[str] = Field(
        default_factory=lambda: ["agent-followup"],
        description="붙일 라벨 목록. 에이전트가 만드는 후속 이슈는 agent-followup만 사용하고 agent-todo는 넣지 않는다.",
    )


class CreateIssueTool(BaseTool):
    name: str = "create_github_issue"
    description: str = (
        "GitHub에 새 이슈를 생성합니다. "
        "QA가 버그·개선 요청 등 후속 작업을 등록할 때 사용합니다. "
        "반드시 labels에 agent-followup만 사용하고, agent-todo는 붙이지 마세요. "
        "agent-todo는 사람이 수동으로 붙이는 전용 라벨입니다."
    )
    args_schema: type[BaseModel] = CreateIssueInput

    def _run(self, title: str, body: str, labels: Optional[List[str]] = None) -> str:
        repo = get_github_client()
        label_list = labels if labels is not None else ["agent-followup"]
        if "agent-todo" in label_list:
            label_list = [l for l in label_list if l != "agent-todo"]
            label_list.append("agent-followup")
        issue = repo.create_issue(title=title, body=body, labels=label_list)
        return f"이슈 생성 완료: #{issue.number} {issue.title} | 라벨: {label_list} | {issue.html_url}"


# ─────────────────────────────────────────────
# PR 생성
# ─────────────────────────────────────────────
class CreatePRInput(BaseModel):
    title: str = Field(description="PR 제목")
    body: str = Field(description="PR 설명")
    head_branch: str = Field(description="소스 브랜치 (예: feature/login)")
    base_branch: str = Field(default="main", description="대상 브랜치")


class CreatePRTool(BaseTool):
    name: str = "create_github_pr"
    description: str = "GitHub Pull Request를 생성합니다."
    args_schema: type[BaseModel] = CreatePRInput

    def _run(self, title: str, body: str, head_branch: str, base_branch: str = "main") -> str:
        repo = get_github_client()
        pr = repo.create_pull(
            title=title,
            body=body,
            head=head_branch,
            base=base_branch,
        )
        return f"PR 생성 완료: {pr.html_url}"
