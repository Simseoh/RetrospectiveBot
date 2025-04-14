import os
import datetime
from github import Github
from collections import defaultdict
from notion_client import Client

# GitHub 토큰 설정
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GitHub 토큰이 필요합니다. GitHub Secret에 PERSONAL_ACCESS_TOKEN을 설정하세요.")

# GitHub 사용자 이름 설정
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME")
if not GITHUB_USERNAME:
    raise ValueError("GitHub 사용자 이름이 필요합니다. 환경 변수 GITHUB_USERNAME을 설정하세요.")

# Notion API 토큰과 데이터베이스 ID 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not NOTION_DATABASE_ID:
    raise ValueError("Notion API 토큰과 데이터베이스 ID가 필요합니다.")

# 회고록 저장 경로 설정
REFLECTION_DIR = "./reflections"
os.makedirs(REFLECTION_DIR, exist_ok=True)


def get_yesterday_commits():
    g = Github(GITHUB_TOKEN)
    user = g.get_user(GITHUB_USERNAME)

    today = datetime.datetime.now().date()
    yesterday = today - datetime.timedelta(days=1)

    since_time = datetime.datetime.combine(yesterday, datetime.time.min)
    until_time = datetime.datetime.combine(today, datetime.time.min)

    print(f"커밋 검색 기간: {since_time} ~ {until_time}")

    commits_by_org_repo = defaultdict(lambda: defaultdict(list))

    for repo in user.get_repos():
        try:
            commits = repo.get_commits(author=GITHUB_USERNAME, since=since_time, until=until_time)
            for commit in commits:
                commits_by_org_repo["Personal"][repo.name].append(commit)
        except Exception as e:
            print(f"개인 레포지토리 {repo.name} 검색 중 오류: {e}")

    for org in user.get_orgs():
        for repo in org.get_repos():
            try:
                commits = repo.get_commits(author=GITHUB_USERNAME, since=since_time, until=until_time)
                for commit in commits:
                    commits_by_org_repo[org.login][repo.name].append(commit)
            except Exception as e:
                print(f"조직 {org.login}의 레포지토리 {repo.name} 검색 중 오류: {e}")

    return commits_by_org_repo, yesterday


def generate_reflection(commits_by_org_repo, reflection_date):
    reflection = f"# {reflection_date.strftime('%Y년 %m월 %d일')} GitHub 활동 회고\n\n"

    has_commits = any(
        any(commits for commits in repos.values())
        for repos in commits_by_org_repo.values()
    )

    if not has_commits:
        reflection += "이 날은 GitHub에 커밋한 내용이 없습니다.\n"
        return reflection

    total_commits = 0
    for org, repos in commits_by_org_repo.items():
        org_commit_count = sum(len(commits) for commits in repos.values())
        if org_commit_count == 0:
            continue

        total_commits += org_commit_count
        reflection += f"## {org} ({org_commit_count}개 커밋)\n\n"

        for repo_name, commits in repos.items():
            if not commits:
                continue

            reflection += f"### {repo_name} ({len(commits)}개 커밋)\n\n"
            commit_messages = [commit.commit.message.split('\n')[0] for commit in commits]

            reflection += "#### 주요 활동\n\n"
            for message in commit_messages:
                reflection += f"- {message}\n"

            try:
                largest_commit = max(commits, key=lambda c: c.stats.total)
                message_line = largest_commit.commit.message.split('\n')[0]
                reflection += "\n#### 가장 큰 변경사항\n"
                reflection += f"- {message_line}\n"
                reflection += f"- 추가: {largest_commit.stats.additions}줄, 삭제: {largest_commit.stats.deletions}줄\n"
            except Exception as e:
                print(f"가장 큰 변경사항 파악 중 오류: {e}")

            reflection += "\n"

    reflection += "## 총 요약\n\n"
    reflection += f"이 날 총 {total_commits}개의 커밋을 수행했습니다.\n\n"

    reflection += "## 자가 회고\n\n"
    reflection += "- 오늘의 성과: \n"
    reflection += "- 어려웠던 점: \n"
    reflection += "- 내일의 계획: \n"

    return reflection


def save_to_notion(reflection, reflection_date):
    try:
        notion = Client(auth=NOTION_TOKEN)

        title = f"{reflection_date.strftime('%Y-%m-%d')} GitHub 활동 회고"

        new_page = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "NAME": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                },
                "DATE": {
                    "date": {
                        "start": reflection_date.strftime('%Y-%m-%d')
                    }
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": "GitHub 활동 회고록이 자동으로 생성되었습니다."
                                }
                            }
                        ]
                    }
                },
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "markdown",
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": reflection
                                }
                            }
                        ]
                    }
                }
            ]
        }

        response = notion.pages.create(**new_page)
        print(f"Notion에 회고록이 저장되었습니다: {response['url']}")
        return response['url']

    except Exception as e:
        print(f"Notion에 저장하는 중 오류 발생: {e}")
        raise e


def save_reflection(reflection, reflection_date):
    filename = f"{reflection_date.strftime('%Y-%m-%d')}_github_reflection.md"
    filepath = os.path.join(REFLECTION_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(reflection)

    print(f"회고록이 저장되었습니다: {filepath}")
    return filepath


def main():
    print("일일 회고록 생성 시작")
    try:
        commits_by_org_repo, reflection_date = get_yesterday_commits()
        reflection = generate_reflection(commits_by_org_repo, reflection_date)

        filepath = save_reflection(reflection, reflection_date)

        if NOTION_TOKEN and NOTION_DATABASE_ID:
            notion_url = save_to_notion(reflection, reflection_date)
            print(f"회고록이 Notion에 저장되었습니다: {notion_url}")

    except Exception as e:
        print(f"회고록 생성 중 오류 발생: {e}")
        raise e


if __name__ == "__main__":
    main()
