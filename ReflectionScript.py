# ReflectionScript.py
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

# 회고록 저장 경로 설정 (GitHub에도 저장하는 경우를 위해)
REFLECTION_DIR = "./reflections"
os.makedirs(REFLECTION_DIR, exist_ok=True)


def get_yesterday_commits():
    """어제 사용자가 수행한 모든 커밋을 가져옵니다."""
    g = Github(GITHUB_TOKEN)
    user = g.get_user(GITHUB_USERNAME)

    # 어제 날짜 설정
    today = datetime.datetime.now().date()
    yesterday = today - datetime.timedelta(days=1)

    # 시작 시간: 어제 자정
    since_time = datetime.datetime.combine(yesterday, datetime.time.min)
    # 종료 시간: 오늘 자정
    until_time = datetime.datetime.combine(today, datetime.time.min)

    print(f"커밋 검색 기간: {since_time} ~ {until_time}")

    # 조직 및 레포지토리별 커밋 정리
    commits_by_org_repo = defaultdict(lambda: defaultdict(list))

    # 사용자 개인 레포지토리 검색
    for repo in user.get_repos():
        try:
            commits = repo.get_commits(author=GITHUB_USERNAME, since=since_time, until=until_time)
            for commit in commits:
                commits_by_org_repo["Personal"][repo.name].append(commit)
        except Exception as e:
            print(f"개인 레포지토리 {repo.name} 검색 중 오류: {e}")

    # 사용자가 속한 조직 검색
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
    """커밋 정보를 바탕으로 회고록을 생성합니다."""
    reflection = f"# {reflection_date.strftime('%Y년 %m월 %d일')} GitHub 활동 회고\n\n"

    # 커밋이 없는지 확인
    has_commits = False
    for repos in commits_by_org_repo.values():
        if any(commits for commits in repos.values()):
            has_commits = True
            break

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

            # 커밋 메시지를 분석하여 주요 활동 요약
            commit_messages = [commit.commit.message.split('\n')[0] for commit in commits]
            reflection += "#### 주요 활동\n\n"
            for message in commit_messages:
                reflection += f"- {message}\n"

            # 가장 큰 변경사항 파악
            try:
                largest_commit = max(commits, key=lambda c: c.stats.total)
                reflection += f"\n#### 가장 큰 변경사항\n"
                reflection += f"- {largest_commit.commit.message.split('\n')[0]}\n"
                reflection += f"- 추가: {largest_commit.stats.additions}줄, 삭제: {largest_commit.stats.deletions}줄\n"
            except Exception as e:
                print(f"가장 큰 변경사항 파악 중 오류: {e}")

            reflection += "\n"

    # 총 요약
    reflection += f"## 총 요약\n\n"
    reflection += f"이 날 총 {total_commits}개의 커밋을 수행했습니다.\n\n"

    # 자가 회고 섹션 추가
    reflection += "## 자가 회고\n\n"
    reflection += "- 오늘의 성과: \n"
    reflection += "- 어려웠던 점: \n"
    reflection += "- 내일의 계획: \n"

    return reflection


def save_to_notion(reflection, reflection_date):
    """회고록을 Notion 데이터베이스에 저장합니다."""
    try:
        # Notion 클라이언트 초기화
        notion = Client(auth=NOTION_TOKEN)

        # 제목 생성
        title = f"{reflection_date.strftime('%Y-%m-%d')} GitHub 활동 회고"

        # Notion 페이지 생성
        new_page = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "제목": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                },
                "날짜": {
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

        # Notion에 페이지 생성
        response = notion.pages.create(**new_page)
        print(f"Notion에 회고록이 저장되었습니다: {response['url']}")
        return response['url']

    except Exception as e:
        print(f"Notion에 저장하는 중 오류 발생: {e}")
        raise e


def save_reflection(reflection, reflection_date):
    """회고록을 파일로 저장합니다."""
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

        # 파일로 저장 (선택 사항)
        filepath = save_reflection(reflection, reflection_date)

        # Notion에 저장
        if NOTION_TOKEN and NOTION_DATABASE_ID:
            notion_url = save_to_notion(reflection, reflection_date)
            print(f"회고록이 Notion에 저장되었습니다: {notion_url}")

    except Exception as e:
        print(f"회고록 생성 중 오류 발생: {e}")
        raise e


if __name__ == "__main__":
    main()