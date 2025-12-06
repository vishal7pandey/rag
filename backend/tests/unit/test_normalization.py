from backend.core.normalization import TextNormalizer


def test_normalizer_collapses_spaces() -> None:
    normalizer = TextNormalizer()
    text = "Hello    world  with   spaces"
    result = normalizer.normalize(text)
    assert "    " not in result
    assert "Hello world with spaces" in result


def test_normalizer_removes_control_characters() -> None:
    normalizer = TextNormalizer()
    text = "Hello\x00World\x01Test"
    result = normalizer.normalize(text)
    assert "\x00" not in result
    assert "\x01" not in result
    assert "Hello" in result and "World" in result


def test_normalizer_normalizes_line_endings() -> None:
    normalizer = TextNormalizer()
    text = "Line 1\r\nLine 2\nLine 3"
    result = normalizer.normalize(text)
    assert "\r" not in result
    assert result.count("\n") >= 2


def test_normalizer_removes_empty_lines() -> None:
    normalizer = TextNormalizer()
    text = "Line 1\n\n\n\n\nLine 2"
    result = normalizer.normalize(text)
    assert "Line 1" in result and "Line 2" in result


def test_normalizer_detects_empty_page() -> None:
    normalizer = TextNormalizer()

    assert normalizer.is_empty_page("")
    assert normalizer.is_empty_page("   \n  \t  ")
    assert normalizer.is_empty_page("a b")  # Only 2 words, below threshold
    assert not normalizer.is_empty_page("This is a real page with content and words")
