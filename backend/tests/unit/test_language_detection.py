from backend.core.language_detection import LanguageDetector


def test_detector_identifies_english() -> None:
    detector = LanguageDetector()
    text = "This is an English document with multiple sentences about various topics."
    lang = detector.detect(text)
    assert lang == "en"


def test_detector_identifies_french() -> None:
    detector = LanguageDetector()
    text = "Ceci est un document français avec plusieurs phrases sur des sujets divers."
    lang = detector.detect(text)
    assert lang == "fr"


def test_detector_falls_back_to_default() -> None:
    detector = LanguageDetector()
    text = "abc def ghi jkl"  # Random non-words
    lang = detector.detect(text, default="en")
    assert lang == "en"
