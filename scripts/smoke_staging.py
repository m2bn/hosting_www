import argparse
import json
import sys
import urllib.error
import urllib.request


def check_url(name, url, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": "staging-smoke/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            ok = 200 <= status < 400
            return {"name": name, "url": url, "status": status, "ok": ok}
    except urllib.error.HTTPError as exc:
        return {"name": name, "url": url, "status": exc.code, "ok": False}
    except urllib.error.URLError as exc:
        return {"name": name, "url": url, "status": None, "ok": False, "error": str(exc.reason)}


def main():
    parser = argparse.ArgumentParser(description="Run staging smoke checks after deployment.")
    parser.add_argument("--api-url", required=True, help="Staging API base URL, for example https://api.staging.example.com")
    parser.add_argument("--dashboard-url", required=True, help="Staging dashboard URL, for example https://app.staging.example.com")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    dashboard_url = args.dashboard_url.rstrip("/")
    checks = [
        check_url("api-health", f"{api_url}/healthz", args.timeout),
        check_url("api-live", f"{api_url}/livez", args.timeout),
        check_url("dashboard", dashboard_url, args.timeout),
    ]
    print(json.dumps({"environment": "staging", "checks": checks}, indent=2))
    return 0 if all(check["ok"] for check in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
