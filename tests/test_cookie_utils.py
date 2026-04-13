import json
import tempfile
import unittest
from pathlib import Path

from app.utils.cookies import normalize_cookie_text, save_normalized_cookie_text


class CookieUtilsTests(unittest.TestCase):
    def test_save_normalized_cookie_text_preserves_netscape_cookie_files(self):
        raw_text = (
            "# Netscape HTTP Cookie File\n"
            ".youtube.com\tTRUE\t/\tTRUE\t1810041475\tPREF\tf4=4000000\n"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            destination = Path(tmp_dir) / "cookies.txt"
            result = save_normalized_cookie_text(raw_text, destination)

            self.assertEqual("netscape", result.source_format)
            self.assertEqual(raw_text, destination.read_text(encoding="utf-8"))

    def test_normalize_cookie_text_accepts_cookie_header_prefix(self):
        result = normalize_cookie_text(
            "Cookie: SAPISID=value123; __Secure-1PSID=secret456; PREF=f4=4000000"
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("header", result.source_format)
        self.assertIn("\tSAPISID\tvalue123", result.netscape_text)
        self.assertIn("\t__Secure-1PSID\tsecret456", result.netscape_text)

    def test_normalize_cookie_text_accepts_json_cookie_wrapper(self):
        result = normalize_cookie_text(
            json.dumps(
                {
                    "cookies": [
                        {
                            "domain": ".youtube.com",
                            "expirationDate": 1810041452.36,
                            "hostOnly": False,
                            "httpOnly": True,
                            "name": "__Secure-3PSID",
                            "path": "/",
                            "secure": True,
                            "session": False,
                            "value": "value123",
                        }
                    ]
                }
            )
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("json", result.source_format)
        self.assertIn("#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1810041452\t__Secure-3PSID\tvalue123", result.netscape_text)


if __name__ == "__main__":
    unittest.main()
