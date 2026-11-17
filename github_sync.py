import os
import base64
import requests
import datetime
from typing import Tuple, Dict, Any

GITHUB_API_URL = "https://api.github.com"
DEFAULT_REPO = "sukmaaji002/Aplikasi-Curah-Hujan"
DEFAULT_BRANCH = "main"

def get_github_config(secrets_dict=None) -> Dict[str, str]:
    """
    Mengambil konfigurasi kredensial GitHub dari Streamlit secrets atau environment variables.
    Aman dan tidak pernah mengekspos token rahasia ke publik.
    """
    token = ""
    repo = DEFAULT_REPO
    branch = DEFAULT_BRANCH

    if secrets_dict is not None:
        try:
            token = secrets_dict.get("GITHUB_TOKEN", "") or secrets_dict.get("github_token", "")
            repo = secrets_dict.get("GITHUB_REPO", DEFAULT_REPO) or secrets_dict.get("github_repo", DEFAULT_REPO)
            branch = secrets_dict.get("GITHUB_BRANCH", DEFAULT_BRANCH) or secrets_dict.get("github_branch", DEFAULT_BRANCH)
        except Exception:
            pass

    if not token:
        token = os.environ.get("GITHUB_TOKEN", "")
        repo = os.environ.get("GITHUB_REPO", repo)
        branch = os.environ.get("GITHUB_BRANCH", branch)

    return {
        "token": str(token).strip(),
        "repo": str(repo).strip(),
        "branch": str(branch).strip()
    }


def is_github_configured(secrets_dict=None) -> bool:
    """Mengecek apakah token GitHub sudah dikonfigurasi."""
    config = get_github_config(secrets_dict)
    return bool(config["token"])


def test_github_connection(secrets_dict=None) -> Tuple[bool, str]:
    """Menguji koneksi ke repositori GitHub menggunakan token yang dikonfigurasi."""
    config = get_github_config(secrets_dict)
    token = config["token"]
    repo = config["repo"]

    if not token:
        return False, "GITHUB_TOKEN belum dikonfigurasi di Streamlit Secrets."

    url = f"{GITHUB_API_URL}/repos/{repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Aplikasi-Curah-Hujan-DPUPR"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            repo_info = resp.json()
            full_name = repo_info.get("full_name", repo)
            return True, f"Terhubung ke repositori GitHub: {full_name}"
        elif resp.status_code == 401:
            return False, "Autentikasi gagal: Token tidak valid atau kedaluwarsa."
        elif resp.status_code == 404:
            return False, f"Repositori '{repo}' tidak ditemukan atau token tidak memiliki izin baca/tulis."
        else:
            return False, f"Respons GitHub ({resp.status_code}): {resp.text[:150]}"
    except Exception as e:
        return False, f"Gagal menghubungi server GitHub: {str(e)}"


def get_file_sha(repo: str, file_path: str, branch: str, token: str) -> str:
    """Mengambil SHA hash dari file yang ada di GitHub untuk keperluan pembaruan berkas."""
    # Pastikan file_path menggunakan slash forward
    clean_path = file_path.replace("\\", "/")
    url = f"{GITHUB_API_URL}/repos/{repo}/contents/{clean_path}?ref={branch}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Aplikasi-Curah-Hujan-DPUPR"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("sha", "")
    except Exception:
        pass
    return ""


def push_file_to_github(
    file_path: str,
    commit_message: str = "",
    secrets_dict=None
) -> Tuple[bool, str]:
    """
    Mengunggah atau memperbarui sebuah file langsung ke repositori GitHub via REST API.
    """
    config = get_github_config(secrets_dict)
    token = config["token"]
    repo = config["repo"]
    branch = config["branch"]

    if not token:
        return False, "GITHUB_TOKEN belum dikonfigurasi di Streamlit Secrets."

    if not os.path.exists(file_path):
        return False, f"Berkas lokal '{file_path}' tidak ditemukan."

    clean_path = file_path.replace("\\", "/")

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        content_b64 = base64.b64encode(file_bytes).decode("utf-8")

        # Dapatkan SHA jika file sudah ada sebelumnya di remote
        current_sha = get_file_sha(repo, clean_path, branch, token)

        if not commit_message:
            commit_message = f"chore(data): auto-sync {clean_path} [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]"

        url = f"{GITHUB_API_URL}/repos/{repo}/contents/{clean_path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Aplikasi-Curah-Hujan-DPUPR"
        }
        payload = {
            "message": commit_message,
            "content": content_b64,
            "branch": branch
        }
        if current_sha:
            payload["sha"] = current_sha

        resp = requests.put(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in (200, 201):
            return True, f"Berhasil disinkronkan ke GitHub ({repo}@{branch})"
        else:
            err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            err_msg = err_data.get("message", resp.text[:200])
            return False, f"GitHub Error ({resp.status_code}): {err_msg}"
    except Exception as e:
        return False, f"Koneksi gagal: {str(e)}"


def sync_all_database_to_github(commit_message: str = "", secrets_dict=None) -> Dict[str, Any]:
    """
    Menyinkronkan seluruh file database (parquet dan log audit) ke GitHub.
    Aman dipanggil: jika token belum diatur, fungsi ini mengembalikan status informatif tanpa menimbulkan error.
    """
    config = get_github_config(secrets_dict)
    if not config["token"]:
        return {
            "configured": False,
            "success": False,
            "message": "GITHUB_TOKEN belum dikonfigurasi. Data baru tetap tersimpan di lokal sistem."
        }

    files_to_sync = ["data_curah_hujan.parquet"]
    if os.path.exists("data_debit_bendung.parquet"):
        files_to_sync.append("data_debit_bendung.parquet")
    if os.path.exists("data_debit_bendung.xlsx"):
        files_to_sync.append("data_debit_bendung.xlsx")
    if os.path.exists("manual_records_log.csv"):
        files_to_sync.append("manual_records_log.csv")
    if os.path.exists("manual_debit_log.csv"):
        files_to_sync.append("manual_debit_log.csv")

    results = {}
    all_success = True
    messages = []

    for fp in files_to_sync:
        msg = commit_message or f"chore(data): pembaruan data curah hujan ({fp}) via Streamlit Cloud"
        ok, res_msg = push_file_to_github(fp, msg, secrets_dict)
        results[fp] = {"success": ok, "message": res_msg}
        if not ok:
            all_success = False
        messages.append(f"{fp}: {res_msg}")

    return {
        "configured": True,
        "success": all_success,
        "details": results,
        "message": " | ".join(messages)
    }
