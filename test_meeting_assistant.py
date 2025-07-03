import unittest
import tempfile
import os
import json
import sqlite3
from unittest.mock import Mock, patch, MagicMock
import numpy as np

# Import our modules
from ai_services import AIServices
from database import DatabaseManager
from utils import FileHandler, format_duration, truncate_text, validate_file_size


class TestAIServices(unittest.TestCase):


    def setUp(self):

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            self.ai_services = AIServices()

    @patch('ai_services.OpenAI')
    def test_init_openai_client(self, mock_openai):

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            ai_services = AIServices()
            mock_openai.assert_called_with(api_key='test_key')

    def test_parse_unstructured_analysis(self):
        """Test parsing of unstructured analysis text"""
        content = """
        EXECUTIVE SUMMARY:
        This was a productive meeting about project planning.

        KEY DECISIONS:
        • Decision to move forward with Plan A
        • Budget approved for Q2

        ACTION ITEMS:
        • John will prepare the report by Friday
        • Team will review documents next week
        """

        result = self.ai_services._parse_unstructured_analysis(content)

        self.assertIn('summary', result)
        self.assertIn('decisions', result)
        self.assertIn('action_items', result)
        self.assertTrue(len(result['decisions']) >= 2)
        self.assertTrue(len(result['action_items']) >= 2)

    @patch('ai_services.OpenAI')
    def test_get_embeddings_success(self, mock_openai):

        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]

        mock_client = Mock()
        mock_client.embeddings.create.return_value = mock_response
        self.ai_services.client = mock_client

        result = self.ai_services.get_embeddings("test text")

        self.assertEqual(result, [0.1, 0.2, 0.3])
        mock_client.embeddings.create.assert_called_once()

    @patch('ai_services.OpenAI')
    def test_get_embeddings_failure(self, mock_openai):

        mock_client = Mock()
        mock_client.embeddings.create.side_effect = Exception("API Error")
        self.ai_services.client = mock_client

        result = self.ai_services.get_embeddings("test text")

        self.assertEqual(result, [])



class TestFileHandler(unittest.TestCase):


    def setUp(self):

        self.file_handler = FileHandler()

    def test_get_file_type_video(self):
        """Test video file type detection"""
        result = self.file_handler.get_file_type("meeting.mp4")
        self.assertEqual(result, 'video')

        result = self.file_handler.get_file_type("recording.avi")
        self.assertEqual(result, 'video')

    def test_get_file_type_audio(self):
        result = self.file_handler.get_file_type("meeting.mp3")
        self.assertEqual(result, 'audio')

        result = self.file_handler.get_file_type("recording.wav")
        self.assertEqual(result, 'audio')

    def test_get_file_type_unknown(self):
        result = self.file_handler.get_file_type("document.txt")
        self.assertEqual(result, 'unknown')

    def test_get_file_hash(self):
        content1 = b"test content"
        content2 = b"different content"

        hash1 = self.file_handler.get_file_hash(content1)
        hash2 = self.file_handler.get_file_hash(content2)
        hash3 = self.file_handler.get_file_hash(content1)

        self.assertNotEqual(hash1, hash2)
        self.assertEqual(hash1, hash3)
        self.assertEqual(len(hash1), 32)

    @patch('utils.subprocess.run')
    def test_check_ffmpeg_available(self, mock_run):
        mock_run.return_value = Mock()

        result = self.file_handler._check_ffmpeg()

        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch('utils.subprocess.run')
    def test_check_ffmpeg_not_available(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        result = self.file_handler._check_ffmpeg()

        self.assertFalse(result)


class TestUtilityFunctions(unittest.TestCase):

    def test_format_duration_seconds(self):
        result = format_duration(45.5)
        self.assertEqual(result, "45.5 seconds")

    def test_format_duration_minutes(self):
        result = format_duration(150)  # 2.5 minutes
        self.assertEqual(result, "2.5 minutes")

    def test_format_duration_hours(self):
        result = format_duration(7200)  # 2 hours
        self.assertEqual(result, "2.0 hours")

    def test_truncate_text_short(self):
        text = "Short text"
        result = truncate_text(text, 20)
        self.assertEqual(result, "Short text")

    def test_truncate_text_long(self):
        text = "This is a very long text that should be truncated"
        result = truncate_text(text, 20)
        self.assertEqual(result, "This is a very lo...")
        self.assertEqual(len(result), 20)

    def test_validate_file_size_valid(self):
        size_bytes = 50 * 1024 * 1024  # 50 MB
        result = validate_file_size(size_bytes, 100)
        self.assertTrue(result)

    def test_validate_file_size_invalid(self):

        size_bytes = 150 * 1024 * 1024  # 150 MB
        result = validate_file_size(size_bytes, 100)
        self.assertFalse(result)


class TestIntegration(unittest.TestCase):

    def setUp(self):

        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()

        with patch('database.AIServices'), patch('ai_services.OpenAI'):
            self.db_manager = DatabaseManager(self.test_db.name)
            self.ai_services = AIServices()

        self.file_handler = FileHandler()

    def tearDown(self):

        self.db_manager.close()
        os.unlink(self.test_db.name)




if __name__ == '__main__':
    # creating suite here
    test_suite = unittest.TestSuite()

    test_classes = [
        TestAIServices,
        # TestDatabaseManager,
        TestFileHandler,
        TestUtilityFunctions,
        TestIntegration
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    print(f"\n{'=' * 50}")
    print(f"TESTS RUN: {result.testsRun}")
    print(f"FAILURES: {len(result.failures)}")
    print(f"ERRORS: {len(result.errors)}")
    print(
        f"SUCCESS RATE: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'=' * 50}")

    exit_code = 0 if result.wasSuccessful() else 1
    exit(exit_code)