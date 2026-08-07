# AWS SES Setup & Production Access

All customer-facing email is sent through Amazon Simple Email Service (SES)
from **info@dristifashions.com**. Two transports are wired in:

- **`ses`** (default) — the SES `SendEmail` API via boto3, using credentials from
  the EC2 instance role (the same path S3 uploads use).
- **`smtp`** — the legacy SES SMTP relay (`email-smtp.ap-south-1.amazonaws.com:587`).

`app/services/email_service.py` tries the configured backend first and falls back
to the other automatically, so a broken transport never silently kills mail.

## Current status

SES is in **Sandbox Mode** (max 200 emails/day, recipients must be verified).
To deliver to *all* users, the account must be moved to **Production Mode**.

## Move out of sandbox (one-time)

1. **Verify the sending identity.** In the AWS console > Amazon SES > Identities,
   verify the **domain `dristifashions.com`**. Verifying a domain also verifies
   every address under it, including `info@dristifashions.com`. Domain verification
   (with DKIM) is strongly preferred over verifying just one address.
   - Add the three DKIM CNAME records, the SPF TXT record and the MX/MAIL FROM
     records SES shows. Confirm status shows **Verified**.
2. **Request production access.** AWS SES console → Account dashboard →
   **Request a review to move out of the sandbox** (in the Sending statistics
   pane). Fill in the form describing the sending purpose:
   - What you send: transactional account OTPs (verification / login / password
     reset) and order lifecycle emails.
   - Volume estimate (e.g. ~100–500 / day, matching the send quota you need).
   - Compliance: opt-in/opt-out approach and how bounces/complaints are handled
     (list-unsubscribe headers are already added).
3. **Await approval.** AWS reviews manually (hours–1 business day typically).
   Once granted, the account is in Production and delivers to any address.

## Verify it's working

```powershell
# From the backend directory
venv\Scripts\python scripts\ses_setup.py                                  # status + mode
venv\Scripts\python scripts\ses_setup.py --send you@example.com           # send a test OTP email
venv\Scripts\python scripts\ses_setup.py --send you@example.com --profile prod   # via a named profile
```

The script prints Sandbox vs Production, whether `info@dristifashions.com` /
the domain is verified, and the current 24-h sending quota.

## Sending quota & sandbox limits

- Sandbox: 200 emails/24h, 1/sec, recipient must be verified.
- Production: quota scales with usage history (default 50/24h → grows). The
  24h limit resets every 15 min (measured on a rolling 24-h window).

## Email flows already implemented

| Flow | Endpoint | Email |
|------|----------|-------|
| Register → verify | `POST /api/v1/auth/register` → `verify-otp` | Verification OTP (`send_otp_email`) |
| OTP login | `POST /api/v1/auth/send-login-otp` → `login-with-otp` | Login OTP (`send_otp_email`, context="login") |
| Forgot password | `POST /api/v1/auth/forgot-password` → `reset-password` | Reset OTP (`send_password_reset_email`) |
| Resend | `POST /api/v1/auth/resend-otp` | OTP resend |

All go through `app/services/email_service.py` `send_email` from **`
info@dristifashions.com`**.

## Env vars

```
EMAIL_BACKEND=ses|smtp
SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL
SES_REGION            # defaults ap-south-1
SES_ACCESS_KEY_ID     # optional; leave empty to use the EC2/CLI role
SES_SECRET_ACCESS_KEY
SES_CONFIGURATION_SET # optional; enables bounce/complaint + open/click tracking
```

If you create a ConfigurationSet in SES you can enable event destinations
(SNS/SES event publishing) and reference it via `SES_CONFIGURATION_SET`.