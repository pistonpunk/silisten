import unittest

from silisten.hotkey import KEYS, MODIFIERS, parse_chord


class ParseChord(unittest.TestCase):
    def test_shift_tab_q(self):
        requirements, trigger = parse_chord("Shift+Tab+Q")
        self.assertEqual(trigger, KEYS["q"])
        self.assertIn(MODIFIERS["shift"], requirements)
        self.assertIn(frozenset({KEYS["tab"]}), requirements)

    def test_single_key(self):
        requirements, trigger = parse_chord("f9")
        self.assertEqual(requirements, [])
        self.assertEqual(trigger, KEYS["f9"])

    def test_aliases_collapse(self):
        requirements, _ = parse_chord("Ctrl+Control+Alt+Space")
        self.assertEqual(len(requirements), 2)
        self.assertIn(MODIFIERS["ctrl"], requirements)
        self.assertIn(MODIFIERS["alt"], requirements)

    def test_detects_every_family(self):
        requirements, trigger = parse_chord("shift+ctrl+alt+meta+x")
        self.assertEqual(trigger, KEYS["x"])
        self.assertEqual(len(requirements), 4)

    def test_rejects_bad_input(self):
        for chord in ("", "Q+Shift", "Ctrl+Nope", "Hyper+Q", "Shift"):
            with self.assertRaises(ValueError, msg=chord):
                parse_chord(chord)

    def test_case_and_spaces(self):
        requirements, trigger = parse_chord(" shift + tab + q ")
        self.assertEqual(trigger, KEYS["q"])
        self.assertEqual(len(requirements), 2)


if __name__ == "__main__":
    unittest.main()
