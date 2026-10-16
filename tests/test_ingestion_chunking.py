import unittest

from app.ingestion.chunking import split_text


class SplitTextTests(unittest.TestCase):
    def test_collapses_whitespace_before_splitting(self):
        self.assertEqual(
            split_text("  alfa\t beta\n gamma  ", size=32, overlap=0),
            ["alfa beta gamma"],
        )

    def test_chunks_have_the_requested_overlap(self):
        self.assertEqual(
            split_text("abcdefghijklmnopqrst", size=8, overlap=3),
            ["abcdefgh", "fghijklm", "klmnopqr", "pqrst"],
        )

    def test_empty_or_whitespace_text_has_no_chunks(self):
        self.assertEqual(split_text("", size=5, overlap=1), [])
        self.assertEqual(split_text(" \n\t ", size=5, overlap=1), [])

    def test_rejects_invalid_size_and_overlap(self):
        for size, overlap in ((0, 0), (5, -1), (5, 5), (5, 6)):
            with self.subTest(size=size, overlap=overlap):
                with self.assertRaises(ValueError):
                    split_text("texto", size=size, overlap=overlap)


if __name__ == "__main__":
    unittest.main()
