#!/usr/bin/env python3
"""
Remove all booking-related rows and Stripe webhook rows; keep the catalog intact.

Preserves ``public.items``, ``public.item_images``, and ``public.item_day_status``.
Deletes ``public.booking_requests`` (CASCADE removes booking_events, booking_documents,
booking_signatures, booking_action_tokens) and truncates ``public.stripe_webhook_events``.

Also removes known booking uploads and generated signing PDFs from Storage (or local
dirs), matching the behavior you want when clearing dev/staging data.

Usage — pick one (the script sets cwd to ``backend/`` so ``.env`` loads; path to the
``.py`` file depends on where you run from):

  # From repo root (…/BFam-Rental)
  python3 backend/scripts/wipe_non_catalog_data.py --yes

  # From backend/ (shell prompt already shows …/backend)
  python3 scripts/wipe_non_catalog_data.py --yes

  # Same as above, one line
  cd backend && python3 scripts/wipe_non_catalog_data.py --yes

Do not use ``python3 backend/scripts/...`` when your current directory is already
``backend/`` (that becomes ``backend/backend/scripts/…`` and fails).

Requires ``SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY`` in ``backend/.env`` (or the environment).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
os.chdir(_BACKEND)
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config import get_settings  # noqa: E402
from app.db import get_supabase  # noqa: E402
from app.services.booking_storage import try_delete_booking_document  # noqa: E402

# Sentinel UUID: PostgREST requires a filter on delete; all real PKs differ from this.
_NIL = "00000000-0000-0000-0000-000000000000"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  python3 backend/scripts/wipe_non_catalog_data.py --yes   # cwd = repo root\n  python3 scripts/wipe_non_catalog_data.py --yes          # cwd = backend/",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required. Confirms you intend to wipe all bookings and webhook events.",
    )
    args = parser.parse_args()
    if not args.yes:
        print("Aborted: re-run with --yes.", file=sys.stderr)
        return 2

    settings = get_settings()
    client = get_supabase()

    pdfs = client.table("booking_documents").select("pdf_path").execute()
    for row in pdfs.data or []:
        try_delete_booking_document(settings, client, row.get("pdf_path"))

    br = (
        client.table("booking_requests")
        .select("drivers_license_path,license_plate_path")
        .execute()
    )
    for row in br.data or []:
        try_delete_booking_document(settings, client, row.get("drivers_license_path"))
        try_delete_booking_document(settings, client, row.get("license_plate_path"))

    client.table("stripe_webhook_events").delete().gte("created_at", "1970-01-01T00:00:00Z").execute()

    del_res = client.table("booking_requests").delete().neq("id", _NIL).execute()
    n = len(del_res.data or [])

    print(
        f"Deleted booking-related storage objects (best-effort), cleared stripe_webhook_events, "
        f"and removed booking_requests (last batch returned {n} row(s); CASCADE removes child tables). "
        "Catalog tables items / item_images / item_day_status were not modified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
