from supabase import Client


def load_images_for_items(client: Client, item_ids: list[str]) -> dict[str, list[dict]]:
    if not item_ids:
        return {}
    res = (
        client.table("item_images")
        .select("id,item_id,url,sort_order")
        .in_("item_id", item_ids)
        .order("sort_order")
        .execute()
    )
    rows = res.data or []
    by_item: dict[str, list[dict]] = {}
    for r in rows:
        by_item.setdefault(r["item_id"], []).append(r)
    return by_item
