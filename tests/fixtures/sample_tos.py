"""
tests/fixtures/sample_tos.py
Real-world TOS snippets with known predatory patterns — used in pytest tests.
"""

# ── Predatory TOS Sample (HIGH risk expected) ─────────────────────────────────
# Inspired by real TOS patterns from major platforms

PREDATORY_TOS = """
TERMS OF SERVICE — EFFECTIVE DATE: JANUARY 1, 2024

1. AUTOMATIC RENEWAL
Your subscription will automatically renew at the end of each billing period 
at the then-current rate. We reserve the right to change pricing at any time 
with 3 days notice. Cancellation requests must be submitted in writing via 
certified mail 60 days prior to renewal date. Failure to cancel by this 
deadline constitutes your agreement to pay the renewal fee in full.

2. BINDING ARBITRATION
YOU AGREE THAT ANY DISPUTE ARISING OUT OF OR RELATED TO THESE TERMS OR OUR 
SERVICES WILL BE RESOLVED BY BINDING ARBITRATION RATHER THAN IN COURT, 
EXCEPT THAT YOU MAY ASSERT CLAIMS IN SMALL CLAIMS COURT IF YOUR CLAIMS QUALIFY. 
You waive your right to participate in a class action lawsuit or class-wide 
arbitration. Arbitration will be conducted by a single arbitrator selected 
solely by the Company.

3. DATA RIGHTS
By using this service, you grant us a perpetual, irrevocable, worldwide, 
royalty-free license to use, reproduce, modify, adapt, publish, translate, 
and distribute any content you submit, post, or display on or through the 
service for any purpose, including commercial purposes, without compensation 
to you. We may share your personal data with third-party partners for 
marketing purposes unless you opt out by contacting us in writing.

4. LIABILITY LIMITATION
TO THE MAXIMUM EXTENT PERMITTED BY LAW, THE COMPANY SHALL NOT BE LIABLE FOR 
ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, 
INCLUDING LOSS OF PROFITS, DATA, USE, GOODWILL, OR OTHER INTANGIBLE LOSSES, 
RESULTING FROM YOUR ACCESS TO OR USE OF (OR INABILITY TO ACCESS OR USE) 
THE SERVICE. Our total liability to you for all claims shall not exceed the 
amount you paid us in the last 30 days.

5. UNILATERAL MODIFICATION
We reserve the right to modify these terms at any time. Your continued use 
of the service after any modification constitutes your acceptance of the 
new terms. We are not required to provide you with notice of any changes.

6. ACCOUNT TERMINATION
We may terminate or suspend your account at any time, for any reason or no 
reason, without notice or liability to you. Upon termination, you forfeit 
all unused credits, subscription time, and any data stored in your account.
"""

# ── Clean / Fair TOS Sample (LOW risk expected) ───────────────────────────────

CLEAN_TOS = """
TERMS OF SERVICE — PLAIN ENGLISH EDITION

1. CANCELLATION
You can cancel your subscription at any time from your account dashboard. 
You will not be charged after cancellation and we'll refund any unused 
portion of your current billing period within 5 business days.

2. DISPUTES
If you have a dispute with us, please contact our support team first. 
We're committed to resolving issues directly. If we can't resolve it, 
disputes will be handled in your local court.

3. YOUR DATA
Your content is yours. We only use your data to provide the service you 
signed up for. We do not sell your personal data to third parties. 
You can download or delete your data at any time.

4. CHANGES TO TERMS
If we make significant changes to these terms, we'll notify you by email 
at least 30 days in advance. You can cancel without penalty if you disagree 
with the new terms.
"""

# ── Edge case: Empty / minimal text ───────────────────────────────────────────
EMPTY_TOS = ""
SHORT_TOS = "By using this service you agree to our terms."
