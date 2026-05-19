from django.db import migrations


def rename_console_session_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DO $$
            BEGIN
                IF to_regclass('console_ses_user_id_opened_at_idx') IS NOT NULL
                   AND to_regclass('console_ses_user_idx') IS NULL THEN
                    ALTER INDEX console_ses_user_id_opened_at_idx RENAME TO console_ses_user_idx;
                END IF;

                IF to_regclass('console_ses_cont_id_opened_at_idx') IS NOT NULL
                   AND to_regclass('console_ses_cont_idx') IS NULL THEN
                    ALTER INDEX console_ses_cont_id_opened_at_idx RENAME TO console_ses_cont_idx;
                END IF;
            END $$;
            """
        )


def restore_console_session_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DO $$
            BEGIN
                IF to_regclass('console_ses_user_idx') IS NOT NULL
                   AND to_regclass('console_ses_user_id_opened_at_idx') IS NULL THEN
                    ALTER INDEX console_ses_user_idx RENAME TO console_ses_user_id_opened_at_idx;
                END IF;

                IF to_regclass('console_ses_cont_idx') IS NOT NULL
                   AND to_regclass('console_ses_cont_id_opened_at_idx') IS NULL THEN
                    ALTER INDEX console_ses_cont_idx RENAME TO console_ses_cont_id_opened_at_idx;
                END IF;
            END $$;
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("containers", "0007_seed_ml_workspace_templates"),
    ]

    operations = [
        migrations.RunPython(
            rename_console_session_indexes,
            restore_console_session_indexes,
        ),
    ]
