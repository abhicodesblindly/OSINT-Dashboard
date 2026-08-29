import re
import asyncio
import os
import subprocess
import sys
from .utils import safe_request, build_response, format_timestamp


async def scan_email(email: str) -> dict:
    """Main email scan orchestrator.

    1. Validate format
    2. Extract metadata (domain, provider)
    3. Query XposedOrNot for breach data (free, no key)
    4. Query HaveIBeenPwned (optional, needs API key)
    5. Run holehe for account-registration checks
    6. Return consolidated result
    """
    # Step 1: Validate
    if not validate_email(email):
        return build_response(False, error="Invalid email address format")

    # Step 2: Extract metadata
    metadata = extract_email_metadata(email)

    # Step 3: Breach check — XposedOrNot (free, no key)
    breaches = await check_breaches_xon(email)

    # Step 4: Breach check — HIBP (optional)
    hibp_breaches = await check_breaches_hibp(email)
    if hibp_breaches:
        breaches.extend(hibp_breaches)

    # Step 5: Account registration checks — holehe
    accounts = await check_email_accounts(email)

    # Step 6: Build result
    result = {
        "input": email,
        "metadata": metadata,
        "breaches": breaches,
        "accounts": accounts,
        "scan_timestamp": format_timestamp(),
    }

    return build_response(True, data=result)


def validate_email(email: str) -> bool:
    """Validate email format with a permissive regex."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def extract_email_metadata(email: str) -> dict:
    """Extract structural metadata from an email address."""
    parts = email.split("@")
    username = parts[0]
    domain = parts[1]

    providers = {
        "gmail.com": "Google Gmail",
        "googlemail.com": "Google Gmail",
        "yahoo.com": "Yahoo Mail",
        "yahoo.co.in": "Yahoo Mail",
        "outlook.com": "Microsoft Outlook",
        "hotmail.com": "Microsoft Hotmail",
        "live.com": "Microsoft Live",
        "msn.com": "Microsoft MSN",
        "icloud.com": "Apple iCloud",
        "me.com": "Apple iCloud",
        "mac.com": "Apple iCloud",
        "aol.com": "AOL Mail",
        "protonmail.com": "ProtonMail",
        "proton.me": "ProtonMail",
        "tutanota.com": "Tutanota",
        "zoho.com": "Zoho Mail",
        "yandex.com": "Yandex Mail",
        "mail.ru": "Mail.ru",
        "gmx.com": "GMX Mail",
        "fastmail.com": "FastMail",
    }

    provider = providers.get(domain.lower(), "Custom / Corporate Domain")

    return {
        "email": email,
        "username": username,
        "domain": domain,
        "provider": provider,
        "format_valid": True,
    }


# ── Breach Checks ──────────────────────────────────────────────────────────────


async def check_breaches_xon(email: str) -> list:
    """Check email breaches via XposedOrNot (free, no API key required)."""
    breaches = []

    url = f"https://api.xposedornot.com/v1/check-email/{email}"
    result = await safe_request(url, timeout=20.0)

    if result["success"] and result.get("data"):
        data = result["data"]
        if isinstance(data, dict):
            # XON returns breach info in several possible shapes
            breach_list = data.get(
                "breaches",
                data.get("ExposedBreaches", {}).get("breaches_details", []),
            )
            if isinstance(breach_list, list):
                for b in breach_list:
                    if isinstance(b, dict):
                        breaches.append(
                            {
                                "name": b.get("breach", b.get("name", "Unknown")),
                                "domain": b.get("domain", "N/A"),
                                "date": b.get("xposed_date", b.get("date", "N/A")),
                                "data_types": b.get(
                                    "xposed_data", b.get("data_classes", "N/A")
                                ),
                                "records": b.get(
                                    "xposed_records", b.get("records", "N/A")
                                ),
                                "source": "XposedOrNot",
                            }
                        )
                    elif isinstance(b, str):
                        breaches.append(
                            {
                                "name": b,
                                "domain": "N/A",
                                "date": "N/A",
                                "data_types": "N/A",
                                "records": "N/A",
                                "source": "XposedOrNot",
                            }
                        )
            elif isinstance(breach_list, str):
                for name in breach_list.split(","):
                    name = name.strip()
                    if name:
                        breaches.append(
                            {
                                "name": name,
                                "domain": "N/A",
                                "date": "N/A",
                                "data_types": "N/A",
                                "records": "N/A",
                                "source": "XposedOrNot",
                            }
                        )

    return breaches


async def check_breaches_hibp(email: str) -> list:
    """Check HaveIBeenPwned (requires API key in .env)."""
    api_key = os.environ.get("HIBP_API_KEY", "").strip()
    if not api_key:
        return []

    url = (
        f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        f"?truncateResponse=false"
    )
    headers = {"hibp-api-key": api_key, "user-agent": "OSINT-Dashboard"}

    result = await safe_request(url, headers=headers, timeout=15.0)

    if result["success"] and isinstance(result.get("data"), list):
        breaches = []
        for b in result["data"]:
            breaches.append(
                {
                    "name": b.get("Name", "Unknown"),
                    "domain": b.get("Domain", "N/A"),
                    "date": b.get("BreachDate", "N/A"),
                    "data_types": ", ".join(b.get("DataClasses", [])),
                    "records": b.get("PwnCount", "N/A"),
                    "source": "HaveIBeenPwned",
                }
            )
        return breaches

    return []


# ── Account Registration Checks ───────────────────────────────────────────────


async def check_email_accounts(email: str) -> list:
    """Check email registration across platforms using holehe.

    Tries the programmatic API first, falls back to subprocess CLI.
    """
    # Attempt 1: programmatic holehe
    try:
        result = await _run_holehe(email)
        if result:
            return result
    except Exception:
        pass

    # Attempt 2: holehe CLI subprocess
    try:
        result = await asyncio.to_thread(_run_holehe_subprocess, email)
        if result:
            return result
    except Exception:
        pass

    return []


async def _run_holehe(email: str) -> list:
    """Run holehe programmatically via its internal module API."""
    try:
        import httpx as hx
        from holehe.core import import_submodules
        import holehe.modules

        modules = import_submodules(holehe.modules)
        out = []

        async with hx.AsyncClient(timeout=hx.Timeout(15.0)) as client:
            tasks = []
            for module_name, module in modules.items():
                try:
                    if hasattr(module, module_name):
                        fn = getattr(module, module_name)
                        tasks.append(fn(email, client, out))
                except Exception:
                    continue

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        accounts = []
        for item in out:
            if isinstance(item, dict):
                accounts.append(
                    {
                        "platform": item.get("name", "Unknown"),
                        "registered": item.get("exists", False),
                        "method": item.get(
                            "emailrecovery", item.get("phoneNumber", "N/A")
                        ),
                        "source": "holehe",
                    }
                )

        return accounts if accounts else None

    except ImportError:
        return None
    except Exception:
        return None


def _run_holehe_subprocess(email: str) -> list:
    """Run the holehe CLI as a subprocess and parse output."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "holehe", email, "--only-used", "--no-color"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0 and result.stdout:
            accounts = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("*") or line.startswith("-"):
                    continue
                if "[+]" in line:
                    platform = line.split("[+]")[-1].strip().split(" ")[0]
                    if platform:
                        accounts.append(
                            {"platform": platform, "registered": True, "source": "holehe"}
                        )
                elif "[-]" in line:
                    platform = line.split("[-]")[-1].strip().split(" ")[0]
                    if platform:
                        accounts.append(
                            {"platform": platform, "registered": False, "source": "holehe"}
                        )
            return accounts if accounts else None
        return None
    except Exception:
        return None
