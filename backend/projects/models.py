from django.db import models


class Project(models.Model):
    id = models.UUIDField(primary_key=True)
    user_id = models.UUIDField(db_index=True)
    name = models.TextField()
    description = models.TextField(blank=True, null=True)
    slug = models.TextField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False  # Supabase owns the schema
        db_table = "projects"
        ordering = ["-created_at"]
