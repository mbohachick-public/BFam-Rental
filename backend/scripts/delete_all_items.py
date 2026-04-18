#!/usr/bin/env python3
"""
Delete every row in public.items (and dependent rows via ON DELETE CASCADE).

Also removes booking uploads and catalog images from Supabase Storage or local dirs
(using the same helpers as the API), so you do not leave orphaned files.

Usage — from repo root: ``python3 backend/scripts/delete_all_items.py --yes`` —
from ``backend/``: ``python3 scripts/delete_all_items.py --yes`` (do not prefix
``backend/`` again if you are already inside ``backend/``).

  cd backend && python3 scripts/delete_all_items.py --yes

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in backend/.env (or the environment).
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
from app.services.item_images_storage import try_delete_item_image_for_url  # noqa: E402

_DELETE_CHUNK = 200


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required. Confirms you intend to wipe all catalog items and related data.",
    )
    args = parser.parse_args()
    if not args.yes:
        print("Aborted: re-run with --yes to delete all items.", file=sys.stderr)
        return 2

    settings = get_settings()
    client = get_supabase()

    br = (
        client.table("booking_requests")
        .select("drivers_license_path,license_plate_path")
        .execute()
    )
    for row in br.data or []:
        try_delete_booking_document(settings, client, row.get("drivers_license_path"))
        try_delete_booking_document(settings, client, row.get("license_plate_path"))

    img_res = client.table("item_images").select("url").execute()
    for row in img_res.data or []:
        try_delete_item_image_for_url(settings, client, str(row["url"]))

    items_res = client.table("items").select("id").execute()
    ids = [str(r["id"]) for r in (items_res.data or [])]
    for i in range(0, len(ids), _DELETE_CHUNK):
        chunk = ids[i : i + _DELETE_CHUNK]
        client.table("items").delete().in_("id", chunk).execute()

    print(
        f"Removed files for bookings/images, then deleted {len(ids)} item(s). "
        "Postgres CASCADE removed booking_requests, item_images, and item_day_status."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
