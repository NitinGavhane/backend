"""
AWS SES setup/health script.

Run from the backend directory:
    venv\\Scripts\\python scripts\\ses_setup.py          # status check
    venv\\Scripts\\python scripts\\ses_setup.py --send you@example.com   # send a test email

It reports:
  - whether the account is in Sandbox or Production mode,
  - which sender identities/domains are verified,
  - your current sending quota.

Moving SES out of Sandbox (see the checklist in scripts/README_SES.md):
  1) Verify the domain dristifashions.com (Create identity -> Domain) in SES.
     This verifies info@dristifashions.com automatically.
  2) Open "Request production access" under Account dashboard -> 'Sending
     statistics' -> 'Request a review to move out of the sandbox'.
  3) AWS support approves after a manual review (DKIM, MX, spf plus your
     use case). Once Production is granted, sends to any address succeed.

Credentials come from the EC2 instance role, or the standard boto3 chain
(env vars / ~/.aws/credentials). Use --region/--profile to override.
"""

import argparse
import sys

# Allow running as `python scripts/ses_setup.py` from the backend root.
if __name__ == "__main__" and __package__ is None:
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.core.config import settings

    REGION = settings.SES_REGION
    SOURCE = settings.SMTP_FROM_EMAIL
else:
    from app.core.config import settings

    REGION = settings.SES_REGION
    SOURCE = settings.SMTP_FROM_EMAIL


def get_ses_client(profile: str | None):
    import boto3

    kwargs = {"region_name": REGION}
    if profile:
        boto3.setup_default_session(profile_name=profile)
    return boto3.client("ses", **kwargs)


def status_report(client) -> dict:
    # get_identity_verification_attributes REQUIRES an Identities list, so fetch
    # the identity names first, then their verification status.
    identities = []
    try:
        listed = client.list_identities()
        emails = listed.get("Identities", [])
        if emails:
            resp = client.get_identity_verification_attributes(Identities=emails)
            for identity, info in resp.get("VerificationAttributes", {}).items():
                identities.append((identity, info.get("VerificationStatus")))
    except Exception as exc:  # noqa: BLE001
        print(f"(could not read identities: {exc})")
        identities = [("(unknown)", None)]

    quota_resp = client.get_send_quota()
    return {
        "region": REGION,
        "source": SOURCE,
        "identities": identities,
        "quota": {
            "max24HourSend": quota_resp.get("Max24HourSend"),
            "maxSendRate": quota_resp.get("MaxSendRate"),
            "sentLast24Hours": quota_resp.get("SentLast24Hours"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AWS SES status / send a test email.")
    parser.add_argument("--check", action="store_true", help="Print sandbox status and verified identities")
    parser.add_argument("--send", dest="send_to", metavar="EMAIL", help="Send a test email to this address")
    parser.add_argument("--region", dest="region", help="Override AWS region")
    parser.add_argument("--profile", help="Named AWS CLI profile to use")
    args = parser.parse_args()

    if args.region:
        globals()["REGION"] = args.region
    client = get_ses_client(args.profile)

    if not (args.check or args.send_to):
        args.check = True

    report = status_report(client)

    print("== AWS SES status ==")
    print("Region      :", report["region"])
    print("Sender      :", report["source"])
    print("Identities  :")
    if report["identities"]:
        for ident, st in report["identities"]:
            print(f"   - {ident:<45} {st}")
    else:
        print("   (none verified)")
    q = report["quota"]
    print("Quota       : sent {:.0f}/{:.0f} last 24h, max rate {:.0f}/sec".format(
        q["sentLast24Hours"] or 0, q["max24HourSend"] or 0, q["maxSendRate"] or 0
    ))

    sandbox = q["max24HourSend"] == 200.0
    print("Mode        :", "SANDBOX (max 200 emails/day)" if sandbox else "PRODUCTION")
    if sandbox:
        print("  -> still in sandbox: only verified addresses can receive mail.")
        print("     Follow scripts/README.md to move to production.")
    else:
        print(f"  -> production: sending to any address (limit {q['max24HourSend']:.0f}/day).")

    if args.send_to:
        from app.services.email_service import send_otp_email

        print(f"\nSending test OTP email to {args.send_to} (source: {report['source']})...")
        try:
            send_otp_email(args.send_to, "000000", context="verification")
            print("OK: email accepted by SES.")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED: {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())