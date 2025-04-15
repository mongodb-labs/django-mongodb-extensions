from django.contrib.auth.models import User


from ..base import BaseTestCase


class MQLPanelTestCase(BaseTestCase):
    panel_id = "MQLPanel"

    def test_disabled(self):
        config = {
            "DISABLE_PANELS": {
                "django_mongodb_extensions.debug_toolbar.panels.mql.MQLPanel"
            }
        }
        self.assertTrue(self.panel.enabled)
        with self.settings(DEBUG_TOOLBAR_CONFIG=config):
            self.assertFalse(self.panel.enabled)

    def test_not_insert_locals(self):
        """
        Test that the panel does not insert locals() content.
        """
        list(User.objects.filter(username="café"))
        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        self.assertNotIn("djdt-locals", self.panel.content)
