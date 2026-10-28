# tests/test_v2_voice.py
"""
Unit tests for SPIDY Phase V2.1: Neural Voice Engine and Audio Cues.
Tests:
1. Audio cue synthesis, formats, and caching.
2. Voice engine personality switching and voice profiles.
3. Natural speech text sanitization (markdown removal, path simplification).
4. Audio cache path generation and file verification.
5. Voice loop summary generation and voice confirmation integration.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import audio_cues
import voice_engine
from voice_loop import _sanitize_for_tts, _make_spoken_summary, confirm_by_voice


class TestAudioCues(unittest.TestCase):
    """Test futuristic audio cue generation and playback."""

    def test_cue_generation(self):
        """All supported cues should synthesize valid 16-bit PCM arrays and WAV bytes."""
        for cue_name in ["wake", "confirm", "done", "error", "listening", "unknown_fallback"]:
            audio, sample_rate, wav_bytes = audio_cues._generate_cue(cue_name)
            self.assertGreater(len(audio), 0, f"Cue {cue_name} audio array is empty")
            self.assertEqual(sample_rate, 44100)
            self.assertTrue(wav_bytes.startswith(b"RIFF"), f"Cue {cue_name} WAV header invalid")
            self.assertIn(b"WAVE", wav_bytes[:12])

    def test_cue_cache(self):
        """Retrieving cue multiple times should return cached item."""
        cue1 = audio_cues._get_cue("wake")
        cue2 = audio_cues._get_cue("wake")
        self.assertIs(cue1, cue2)

    def test_play_cue_safe(self):
        """play_cue should execute without crashing regardless of hardware state."""
        # Non-blocking
        audio_cues.play_cue("wake", async_play=True)
        # Blocking (mocked playback)
        with mock.patch("sounddevice.play", create=True):
            audio_cues.play_cue("done", async_play=False)


class TestVoiceEngine(unittest.TestCase):
    """Test high-fidelity VoiceEngine features."""

    def setUp(self):
        self.engine = voice_engine.VoiceEngine(personality="jarvis")

    def test_personality_profiles(self):
        """Personalities should correctly configure voice names and honorifics."""
        self.assertEqual(self.engine.personality, "jarvis")
        self.assertEqual(self.engine.voice, "en-GB-RyanNeural")
        self.assertEqual(self.engine.honorific, "Sir")

        # Switch to Friday
        success = self.engine.set_personality("friday")
        self.assertTrue(success)
        self.assertEqual(self.engine.personality, "friday")
        self.assertEqual(self.engine.voice, "en-IE-EmilyNeural")
        self.assertEqual(self.engine.honorific, "Boss")

        # Switch to Edith
        success = self.engine.set_personality("edith")
        self.assertTrue(success)
        self.assertEqual(self.engine.personality, "edith")
        self.assertEqual(self.engine.voice, "en-US-AriaNeural")

        # Invalid personality should return False
        self.assertFalse(self.engine.set_personality("invalid_persona"))

    def test_sanitize_for_speech(self):
        """Sanitizer should remove markdown symbols and simplify paths."""
        raw = "### Found files:\n- `C:\\Users\\pavan\\Desktop\\report.docx`\n- **Important** update!"
        cleaned = self.engine.sanitize_for_speech(raw)
        self.assertNotIn("#", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertIn("report.docx", cleaned)
        self.assertNotIn("C:\\Users", cleaned)

    def test_long_text_truncation(self):
        """Very long text should be truncated naturally to prevent overwhelming speech."""
        long_text = "Sentence one. " * 30
        cleaned = self.engine.sanitize_for_speech(long_text)
        self.assertLess(len(cleaned), 300)

    def test_cache_key_generation(self):
        """Different texts or voices should generate different cache paths."""
        path1 = self.engine._get_cache_path("Hello world")
        path2 = self.engine._get_cache_path("Hello world")
        path3 = self.engine._get_cache_path("Goodbye world")
        self.assertEqual(path1, path2)
        self.assertNotEqual(path1, path3)

    def test_voice_loop_helpers(self):
        """Voice loop helpers should route through VoiceEngine."""
        res = _sanitize_for_tts("Testing `path\\file.txt` **bold**")
        self.assertNotIn("`", res)
        self.assertNotIn("**", res)

        summary = _make_spoken_summary("First line summary.\nSecond line details.")
        self.assertEqual(summary, "First line summary.")


class TestVoiceConfirmation(unittest.TestCase):
    """Test hands-free voice confirmation logic."""

    @mock.patch("voice_loop.speak")
    @mock.patch("voice_loop.listen_for_phrase")
    def test_confirm_positive(self, mock_listen, mock_speak):
        mock_listen.return_value = "yes proceed"
        confirmed = confirm_by_voice("delete_file", "CONFIRM", mock.MagicMock(), mock.MagicMock())
        self.assertTrue(confirmed)

    @mock.patch("voice_loop.speak")
    @mock.patch("voice_loop.listen_for_phrase")
    def test_confirm_negative(self, mock_listen, mock_speak):
        mock_listen.return_value = "no cancel it"
        confirmed = confirm_by_voice("delete_file", "CONFIRM", mock.MagicMock(), mock.MagicMock())
        self.assertFalse(confirmed)


if __name__ == "__main__":
    unittest.main()

