import pytest

from auth_service.services.rich_text_migration import (
    MigrationConfig,
    migration_sql,
    plan_project_migration,
    restore_sql,
    unknown_config_refs,
)
from auth_service.services.segments import src_hash

PID = "860792c9-24f7-43fc-97de-107a31ea7307"
R_EN, R_DE, R_KV, R_RP = (f"00000000-0000-0000-0000-00000000000{i}" for i in range(1, 5))


def _services():
    tb_en = {"title": "IT & Cloud", "body": "**Fast** repairs\n\n- a\n- b"}
    tb_de = {"title": "IT & Cloud DE", "body": "**Schnell**"}
    return [
        {
            "service_key": "hero",
            "service_type_slug": "text_block",
            "content_entries": [
                {
                    "id": R_EN,
                    "locale": "en",
                    "draft_content": tb_en,
                    "published_content": tb_en,
                    "translation_meta": {},
                    "updated_at": "2026-09-27T10:00:00+00:00",
                },
                {
                    "id": R_DE,
                    "locale": "de",
                    "draft_content": tb_de,
                    "published_content": tb_de,
                    "translation_meta": {
                        "title": {"src_hash": src_hash("IT & Cloud")},
                        "body": {"src_hash": "stale0000000000"},
                    },
                    "updated_at": "2026-09-27T10:00:01+00:00",
                },
            ],
        },
        {
            "service_key": "contact_info",
            "service_type_slug": "key_value",
            "content_entries": [
                {
                    "id": R_KV,
                    "locale": "en",
                    "draft_content": {
                        "entries": [
                            {"key": "phone", "value": "+40 7"},
                            {"key": "about", "value": "We & you"},
                        ]
                    },
                    "published_content": {"entries": {"phone": "+40 7", "about": "We & you"}},
                    "translation_meta": {},
                    "updated_at": None,
                },
            ],
        },
        {
            "service_key": "features",
            "service_type_slug": "repeater",
            "content_entries": [
                {
                    "id": R_RP,
                    "locale": "en",
                    "draft_content": {
                        "_schema": [
                            {"key": "title", "label": "T", "type": "string"},
                            {"key": "desc", "label": "D", "type": "richtext"},
                        ],
                        "items": [{"_id": "i1", "title": "A & B", "desc": "*x*"}],
                    },
                    "published_content": {},
                    "translation_meta": {},
                    "updated_at": "2026-09-27T10:00:02+00:00",
                },
            ],
        },
    ]


CFG = MigrationConfig.from_dict(
    {
        "repeaters": {"features": {"title": "inline"}},
        "key_values": {"contact_info": {"about": "inline"}},
    }
)


def _by_id(updates):
    return {u.row_id: u for u in updates}


def test_text_block_converted_in_draft_and_published():
    u = _by_id(plan_project_migration(_services(), CFG, "en"))[R_EN]
    expected = {
        "title": "IT &amp; Cloud",
        "body": "<p><strong>Fast</strong> repairs</p><ul><li><p>a</p></li><li><p>b</p></li></ul>",
    }
    assert u.draft_content == expected
    assert u.published_content == expected


def test_manual_override_hash_follows_converted_source_but_stale_stays_stale():
    u = _by_id(plan_project_migration(_services(), CFG, "en"))[R_DE]
    assert u.translation_meta["title"] == {"src_hash": src_hash("IT &amp; Cloud")}
    assert u.translation_meta["body"] == {"src_hash": "stale0000000000"}


def test_key_value_formats_applied_legacy_list_flattened_plain_untouched():
    u = _by_id(plan_project_migration(_services(), CFG, "en"))[R_KV]
    assert u.draft_content == {
        "entries": {"phone": "+40 7", "about": "We &amp; you"},
        "_formats": {"about": "inline"},
    }
    assert u.published_content["entries"]["phone"] == "+40 7"


def test_repeater_schema_retyped_and_fields_converted():
    u = _by_id(plan_project_migration(_services(), CFG, "en"))[R_RP]
    assert u.draft_content["_schema"][0]["type"] == "inline"
    assert u.draft_content["items"][0] == {
        "_id": "i1",
        "title": "A &amp; B",
        "desc": "<p><em>x</em></p>",
    }
    assert u.published_content is None or u.published_content == {}


def test_unknown_refs_reported():
    cfg = MigrationConfig.from_dict(
        {
            "repeaters": {"features": {"nope": "inline"}, "ghost": {"x": "inline"}},
            "key_values": {"contact_info": {"zzz": "rich"}},
        }
    )
    refs = unknown_config_refs(_services(), cfg)
    assert (
        any("ghost" in r for r in refs)
        and any("nope" in r for r in refs)
        and any("zzz" in r for r in refs)
    )


def test_invalid_config_type_rejected():
    with pytest.raises(ValueError):
        MigrationConfig.from_dict({"repeaters": {"features": {"title": "html"}}})


def test_sql_is_one_atomic_block_with_guards_and_version_flip():
    sql = migration_sql(PID, plan_project_migration(_services(), CFG, "en"))
    assert sql.strip().startswith("do $") and sql.count("do $") == 1
    assert "rich_text_version <> 0" in sql
    assert f"id = '{R_EN}' and updated_at = '2026-09-27T10:00:00+00:00'::timestamptz" in sql
    assert f"id = '{R_KV}' and updated_at is null" in sql
    assert "if not found then raise exception" in sql
    assert "update projects set rich_text_version = 1" in sql


def test_sql_rejects_bad_ids():
    bad = plan_project_migration(_services(), CFG, "en")
    bad[0].row_id = "x'; drop table projects; --"
    with pytest.raises(ValueError):
        migration_sql(PID, bad)


def test_restore_sql_sets_version_back():
    sql = restore_sql(
        PID,
        [
            {
                "id": R_EN,
                "draft_content": {"title": "x"},
                "published_content": {},
                "translation_meta": {},
            }
        ],
    )
    assert "rich_text_version = 0" in sql and f"id = '{R_EN}'" in sql


def _kv_service(key, entries, row_id=R_KV):
    return {
        "service_key": key,
        "service_type_slug": "key_value",
        "content_entries": [
            {
                "id": row_id,
                "locale": "en",
                "draft_content": {"entries": entries},
                "published_content": {"entries": entries},
                "translation_meta": {},
                "updated_at": None,
            },
        ],
    }


def test_kv_flatten_matches_public_api_rules():
    entries = [
        {"key": "phone ", "value": "x"},
        {"key": " ", "value": "skip"},
        {"key": "n"},
        "junk",
        {"key": 5, "value": "y"},
    ]
    cfg = MigrationConfig.from_dict({"key_values": {"kv": {"phone": "inline"}}})
    u = plan_project_migration([_kv_service("kv", entries)], cfg, "en")[0]
    assert u.draft_content["entries"] == {"phone": "x", "n": None}


def test_unlisted_list_shaped_kv_left_untouched_listed_flattened():
    entries = [{"key": "b", "value": "1"}, {"key": "a", "value": "2"}]
    assert plan_project_migration([_kv_service("skills", entries)], MigrationConfig(), "en") == []
    cfg = MigrationConfig.from_dict({"key_values": {"skills": {"a": "inline"}}})
    assert len(plan_project_migration([_kv_service("skills", entries)], cfg, "en")) == 1


def test_sql_rejects_bad_timestamp():
    ups = plan_project_migration(_services(), CFG, "en")
    ups[0].updated_at = "x'; drop table projects; --"
    with pytest.raises(ValueError):
        migration_sql(PID, ups)


def test_sql_rejects_dollar_quote_collision(monkeypatch):
    import auth_service.services.rich_text_migration as m

    monkeypatch.setattr(m.secrets, "token_hex", lambda n: "abc")
    ups = plan_project_migration(_services(), CFG, "en")
    ups[0].draft_content = {"title": "$jabc$ boom"}
    with pytest.raises(ValueError):
        migration_sql(PID, ups)
    ups[0].draft_content = {"title": "$mig_jabc$ boom"}
    with pytest.raises(ValueError):
        migration_sql(PID, ups)


def test_sql_has_missing_project_guard_and_restore_guards_and_null():
    sql = migration_sql(PID, plan_project_migration(_services(), CFG, "en"))
    assert "project not found" in sql
    rsql = restore_sql(
        PID, [{"id": R_EN, "draft_content": None, "published_content": {}, "translation_meta": {}}]
    )
    assert "draft_content = null," in rsql
    assert rsql.count("if not found then raise exception") == 2


def test_cli_streams_survive_cp1252():
    import importlib.util
    import io
    import sys
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "migrate_rich_text.py"
    spec = importlib.util.spec_from_file_location("migrate_rich_text_cli", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    buf = io.BytesIO()
    fake = io.TextIOWrapper(buf, encoding="cp1252")
    old = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = fake
    try:
        mod._configure_streams()
        print("\u0219 \u2192 \u2713")
        fake.flush()
    finally:
        sys.stdout, sys.stderr = old
    assert "\u0219".encode() in buf.getvalue()
