import unittest

from silisten import config, models


class Registry(unittest.TestCase):
    def test_known_speech_model_resolves(self):
        entry = models.speech_repo({"speech_model": "large-v3"})
        self.assertEqual(entry["repo"], "openai/whisper-large-v3")

    def test_unknown_model_is_treated_as_repo_id(self):
        entry = models.speech_repo({"speech_model": "someone/custom-whisper"})
        self.assertEqual(entry["repo"], "someone/custom-whisper")

    def test_default_is_used_when_unset(self):
        entry = models.speech_repo({})
        self.assertEqual(entry["name"], "large-v3")

    def test_romanian_can_be_disabled(self):
        self.assertIsNone(models.romanian_repo({"romanian_model": None}))

    def test_profiles_are_complete(self):
        for name, profile in models.PROFILES.items():
            with self.subTest(profile=name):
                self.assertIn(profile["speech"], models.SPEECH)
                self.assertIn(profile["vad"], models.VAD)
                if profile["romanian"]:
                    self.assertIn(profile["romanian"], models.ROMANIAN)

    def test_apply_profile_updates_config(self):
        cfg = {}
        models.apply_profile(cfg, "fast")
        self.assertEqual(cfg["speech_model"], "small")

    def test_apply_profile_rejects_unknown(self):
        with self.assertRaises(ValueError):
            models.apply_profile({}, "nope")


class Migration(unittest.TestCase):
    def test_old_model_key_becomes_speech_model(self):
        cfg = config.migrate({"model": "openai/whisper-large-v3"})
        self.assertNotIn("model", cfg)
        self.assertEqual(cfg["speech_model"], "openai/whisper-large-v3")

    def test_hub_name_becomes_registry_name(self):
        cfg = config.migrate({"romanian_model": "FraPiz/whisper-large-v3-turbo-moldovan-romanian"})
        self.assertEqual(cfg["romanian_model"], "fra-piz-turbo")

    def test_unknown_fields_survive(self):
        cfg = config.migrate({"custom": 1})
        self.assertEqual(cfg["custom"], 1)


if __name__ == "__main__":
    unittest.main()
