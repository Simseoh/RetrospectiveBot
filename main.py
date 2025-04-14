import os
from github import Github
from datetime import datetime, timedelta
import requests
from collections import defaultdict
from openai import OpenAI  # ✅ 여기 추가

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DB_ID = os.environ["NOTION_DATABASE_ID"]

client = OpenAI(api_key=OPENAI_API_KEY)  # ✅ 여기 변경


def get_commits_grouped_by_repo(token, username, since_days_ago=1):
    g = Github(token)
    user = g.get_user()
    since = datetime.now() - timedelta(days=since_days_ago)
    repo_commits = defaultdict(list)

    for repo in user.get_repos():
        try:
            commits = repo.get_commits(since=since)
            for commit in commits:
                if commit.author and commit.author.login == username:
                    repo_commits[repo.name].append(commit.commit.message)
        except Exception:
            continue

    return repo_commits


def generate_repo_based_retrospective(repo_commits):
    if not repo_commits:
        return "오늘은 커밋 기록이 없습니다."

    formatted = ""
    for repo, messages in repo_commits.items():
        formatted += f"📦 {repo}\n"
        for msg in messages:
            formatted += f"- {msg}\n"
        formatted += "\n"

    prompt = f"""다음은 내가 오늘 작성한 GitHub 커밋 메시지들이야. 레포지토리별로 정리되어 있어:\n\n{formatted}\n이 내용을 바탕으로 각 레포에서 한 일, 느낀 점, 개선점 등을 포함한 회고록을 써줘. 레포별로 항목을 나눠서 정리해줘."""

    response = client.chat.completions.create(  # ✅ 여기 변경
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return response.choices[0].message.content  # ✅ 여기도 수정


def upload_to_notion(notion_token, database_id, title, content):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    data = {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {
                "title": [{"text": {"content": title}}]
            }
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)
    return response.status_code == 200


if __name__ == "__main__":
    repo_commits = get_commits_grouped_by_repo(GITHUB_TOKEN, GITHUB_USERNAME)
    if repo_commits:
        retrospective = generate_repo_based_retrospective(repo_commits)
        today = datetime.now().strftime("%Y-%m-%d")
        success = upload_to_notion(NOTION_TOKEN, NOTION_DB_ID, f"회고록 - {today}", retrospective)
        print("✅ 회고록 업로드 완료!" if success else "❌ 업로드 실패!")
    else:
        print("📭 오늘 작성한 커밋이 없습니다.")
