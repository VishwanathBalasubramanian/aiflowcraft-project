import requests
import base64

def upload_file_to_github(token, repo, file_path, content, commit_message="Add generated code"):
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    # Get current SHA if file exists (for updating)
    response = requests.get(url, headers=headers)
    sha = response.json().get("sha") if response.status_code == 200 else None

    data = {
        "message": commit_message,
        "content": base64.b64encode(content.encode()).decode("utf-8"),
        "branch": "main"
    }

    if sha:
        data["sha"] = sha

    response = requests.put(url, headers=headers, json=data)
    return response.status_code, response.json()
