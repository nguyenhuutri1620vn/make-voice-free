import unittest

from ssml_markup import to_ssml


class ToSsmlTests(unittest.TestCase):
    def test_plain_text_is_wrapped_in_speak(self):
        self.assertEqual(to_ssml("Xin chào"), "<speak>Xin chào</speak>")

    def test_emphasis(self):
        self.assertEqual(
            to_ssml("Đây là *quan trọng* nhé"),
            '<speak>Đây là <emphasis level="strong">quan trọng</emphasis> nhé</speak>',
        )

    def test_pause(self):
        self.assertEqual(
            to_ssml("Một[pause 300ms]hai[pause 0.5s]ba"),
            '<speak>Một<break time="300ms"/>hai<break time="0.5s"/>ba</speak>',
        )

    def test_prosody_block(self):
        self.assertEqual(
            to_ssml("[prosody rate=slow pitch=+2st]chậm[/prosody] nhanh"),
            '<speak><prosody rate="slow" pitch="+2st">chậm</prosody> nhanh</speak>',
        )

    def test_text_is_xml_escaped(self):
        self.assertEqual(
            to_ssml("A < B & C > D"),
            "<speak>A &lt; B &amp; C &gt; D</speak>",
        )

    def test_emphasis_content_is_escaped(self):
        self.assertIn("&amp;", to_ssml("*R&D*"))

    def test_unclosed_prosody_raises(self):
        with self.assertRaises(ValueError):
            to_ssml("[prosody rate=slow]abc")

    def test_stray_closing_prosody_raises(self):
        with self.assertRaises(ValueError):
            to_ssml("abc[/prosody]")

    def test_unsupported_prosody_attribute_raises(self):
        with self.assertRaises(ValueError):
            to_ssml("[prosody foo=bar]x[/prosody]")


if __name__ == "__main__":
    unittest.main()
