import phonenumbers
from phonenumbers import carrier, geocoder, timezone as pn_timezone
import asyncio
import subprocess
import sys
import os
from .utils import safe_request, build_response, format_timestamp


async def scan_phone(phone_number: str) -> dict:
    """Main phone scan orchestrator.

    1. Parse & validate the phone number
    2. Query Numverify for enrichment (if API key set)
    3. Run ignorant for account-registration checks
    4. Return consolidated result
    """
    # Step 1: Validate and parse
    metadata = parse_phone(phone_number)
    if not metadata["valid"]:
        return build_response(
            False, error=metadata.get("error", "Invalid phone number")
        )

    # Step 2: Numverify enrichment (optional)
    numverify_data = await check_numverify(metadata["e164"])
    if numverify_data.get("carrier") and metadata["carrier"] == "Unknown":
        metadata["carrier"] = numverify_data["carrier"]

    # Step 3: Account checks via ignorant
    accounts = await check_phone_accounts(metadata["e164"])

    # Step 4: Build final result
    result = {
        "input": phone_number,
        "metadata": metadata,
        "breaches": [],  # Phone-specific breach APIs can be added here
        "accounts": accounts,
        "numverify": numverify_data if numverify_data.get("success") else None,
        "scan_timestamp": format_timestamp(),
    }

    return build_response(True, data=result)


def parse_phone(phone_number: str) -> dict:
    """Parse and validate a phone number using Google's phonenumbers library.

    Returns a dict with all extracted metadata, or an error dict.
    """
    try:
        parsed = phonenumbers.parse(phone_number, None)

        if not phonenumbers.is_valid_number(parsed):
            # Retry assuming US if no region prefix
            parsed = phonenumbers.parse(phone_number, "US")
            if not phonenumbers.is_valid_number(parsed):
                return {
                    "valid": False,
                    "error": (
                        "Invalid phone number format. "
                        "Use international format with country code (e.g., +14155552671)."
                    ),
                }

        e164 = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )
        international = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
        national = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.NATIONAL
        )

        carrier_name = carrier.name_for_number(parsed, "en") or "Unknown"
        country = geocoder.description_for_number(parsed, "en") or "Unknown"
        timezones = list(pn_timezone.time_zones_for_number(parsed)) or ["Unknown"]

        number_type_map = {
            0: "Fixed Line",
            1: "Mobile",
            2: "Fixed Line or Mobile",
            3: "Toll Free",
            4: "Premium Rate",
            5: "Shared Cost",
            6: "VoIP",
            7: "Personal Number",
            8: "Pager",
            9: "UAN",
            10: "Voicemail",
            27: "Emergency",
            28: "Short Code",
            29: "Standard Rate",
        }

        num_type = phonenumbers.number_type(parsed)
        line_type = number_type_map.get(num_type, "Unknown")
        country_code = parsed.country_code
        region = phonenumbers.region_code_for_number(parsed)

        return {
            "valid": True,
            "e164": e164,
            "international": international,
            "national": national,
            "country_code": f"+{country_code}",
            "region_code": region or "Unknown",
            "country": country,
            "carrier": carrier_name,
            "line_type": line_type,
            "timezones": timezones,
        }
    except phonenumbers.NumberParseException as e:
        return {"valid": False, "error": f"Could not parse phone number: {str(e)}"}
    except Exception as e:
        return {"valid": False, "error": f"Phone parsing error: {str(e)}"}


async def check_phone_accounts(e164_number: str) -> list:
    """Check phone registration across platforms using the ignorant library.

    Falls back to an empty list if ignorant is unavailable.
    """
    try:
        result = await asyncio.to_thread(_run_ignorant_subprocess, e164_number)
        if result:
            return result
    except Exception:
        pass

    return []


def _run_ignorant_subprocess(phone: str) -> list:
    """Run the ignorant CLI as a subprocess and parse its output."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ignorant", phone],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout:
            accounts = []
            lines = result.stdout.strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if "[+]" in line or "exists" in line.lower():
                    platform = (
                        line.split("[+]")[-1].strip()
                        if "[+]" in line
                        else line
                    )
                    platform = (
                        platform.split(":")[0].strip()
                        if ":" in platform
                        else platform
                    )
                    if platform:
                        accounts.append(
                            {"platform": platform, "registered": True, "source": "ignorant"}
                        )
                elif "[-]" in line or "not" in line.lower():
                    platform = (
                        line.split("[-]")[-1].strip()
                        if "[-]" in line
                        else line
                    )
                    platform = (
                        platform.split(":")[0].strip()
                        if ":" in platform
                        else platform
                    )
                    if platform:
                        accounts.append(
                            {"platform": platform, "registered": False, "source": "ignorant"}
                        )
            return accounts if accounts else None
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None


async def check_numverify(e164_number: str) -> dict:
    """Query the Numverify API if a key is available in the environment."""
    api_key = os.environ.get("NUMVERIFY_API_KEY", "").strip()
    if not api_key:
        return {"success": False, "note": "No Numverify API key configured"}

    number = e164_number.lstrip("+")
    url = f"http://apilayer.net/api/validate?access_key={api_key}&number={number}"

    result = await safe_request(url)
    if result["success"] and isinstance(result.get("data"), dict):
        data = result["data"]
        return {
            "success": True,
            "carrier": data.get("carrier", ""),
            "line_type": data.get("line_type", ""),
            "location": data.get("location", ""),
            "country_name": data.get("country_name", ""),
        }
    return {"success": False, "error": result.get("error")}
