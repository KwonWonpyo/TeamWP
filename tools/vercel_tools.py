"""
tools/vercel_tools.py

Vercel API를 사용하는 툴. 배포 상태 조회·트리거 등.
VERCEL_TOKEN이 설정된 경우에만 사용 가능.
"""

import os
from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

try:
    import requests
except ImportError:
    requests = None

VERCEL_API_BASE = "https://api.vercel.com"


def _vercel_headers() -> dict:
    token = os.getenv("VERCEL_TOKEN")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────
# 프로젝트 목록 조회
# ─────────────────────────────────────────────
class ListVercelProjectsInput(BaseModel):
    pass


class ListVercelProjectsTool(BaseTool):
    name: str = "list_vercel_projects"
    description: str = "Vercel에 연결된 프로젝트 목록을 조회합니다. 배포 전 프로젝트 ID 확인용."
    args_schema: type[BaseModel] = ListVercelProjectsInput

    def _run(self) -> str:
        if not requests:
            return "requests 패키지가 필요합니다: pip install requests"
        headers = _vercel_headers()
        if not headers:
            return "VERCEL_TOKEN이 설정되지 않았습니다. .env에 VERCEL_TOKEN을 넣으세요."
        try:
            r = requests.get(f"{VERCEL_API_BASE}/v2/projects", headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            projects = data.get("projects", [])
            if not projects:
                return "Vercel 프로젝트가 없습니다."
            lines = [f"- {p.get('name')} (id: {p.get('id')})" for p in projects[:20]]
            return "\n".join(lines)
        except Exception as e:
            return f"Vercel API 오류: {e}"


# ─────────────────────────────────────────────
# 배포 생성 (트리거)
# ─────────────────────────────────────────────
class CreateDeploymentInput(BaseModel):
    project_id_or_name: str = Field(description="Vercel 프로젝트 ID 또는 이름")
    branch: str = Field(default="main", description="배포할 Git 브랜치")
    description: Optional[str] = Field(default=None, description="배포 설명(선택)")


class CreateDeploymentTool(BaseTool):
    name: str = "create_vercel_deployment"
    description: str = "Vercel 프로젝트에 대해 새 배포를 트리거합니다. Git 브랜치를 지정할 수 있습니다."
    args_schema: type[BaseModel] = CreateDeploymentInput

    def _run(
        self,
        project_id_or_name: str,
        branch: str = "main",
        description: Optional[str] = None,
    ) -> str:
        if not requests:
            return "requests 패키지가 필요합니다: pip install requests"
        headers = _vercel_headers()
        if not headers:
            return "VERCEL_TOKEN이 설정되지 않았습니다."
        try:
            payload = {"name": project_id_or_name, "gitSource": {"ref": branch, "type": "github"}}
            if description:
                payload["meta"] = {"description": description}
            r = requests.post(
                f"{VERCEL_API_BASE}/v13/deployments",
                headers=headers,
                json=payload,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            url = data.get("url") or data.get("alias", [])
            return f"배포 트리거됨: {data.get('id')} | URL: {url}"
        except Exception as e:
            return f"Vercel 배포 오류: {e}"
