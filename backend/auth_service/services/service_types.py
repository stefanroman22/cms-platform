"""The fixed set of CMS service types: slug → (dashboard name, lucide icon).

`project_services.service_type_slug` must be one of these keys; the database
enforces the same list with a CHECK constraint, so adding a type means editing
both this dict and that constraint (in a new migration).
"""

SERVICE_TYPES: dict[str, tuple[str, str]] = {
    "email_config": ("Email Config", "Mail"),
    "file_download": ("File Download", "Download"),
    "floor_plan": ("Floor Plan", "LayoutGrid"),
    "gallery": ("Gallery", "Images"),
    "image": ("Image", "Image"),
    "key_value": ("Key-Value Store", "Hash"),
    "repeater": ("Repeater", "List"),
    "text_block": ("Text Block", "FileText"),
    "theme": ("Theme", "Palette"),
    "video": ("Video", "Video"),
}
