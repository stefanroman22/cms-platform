"""widget_color is no longer dashboard-editable — it must not be a field on the
editable SettingsPatch schema (the public /config read path keeps it)."""

from auth_service.models.booking_admin_schemas import SettingsPatch


def test_settings_patch_has_no_widget_color():
    assert "widget_color" not in SettingsPatch.model_fields
