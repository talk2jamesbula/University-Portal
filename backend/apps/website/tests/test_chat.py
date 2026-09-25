from datetime import timedelta
from unittest import mock

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.admissions.models import AdmissionCycle
from apps.core.testing import make_department, make_programme

URL = "/api/public/chat/"


def ask(question, history=()):
    messages = [*history, {"role": "user", "content": question}]
    return APIClient().post(URL, {"messages": messages}, format="json")


@override_settings(ANTHROPIC_API_KEY="")
class BuiltInAnswerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme(make_department(name="Computer Science"), name="Computer Science", code="CSC")
        today = timezone.localdate()
        AdmissionCycle.objects.create(
            session="2026/2027",
            application_fee=10000,
            opens_on=today - timedelta(days=5),
            closes_on=today + timedelta(days=30),
            min_utme_score=180,
        )

    def setUp(self):
        cache.clear()

    def test_answers_common_questions_from_live_data(self):
        fee = ask("How much is the application fee?").data
        self.assertEqual(fee["source"], "faq")
        self.assertIn("₦10,000.00", fee["reply"])
        self.assertIn(
            "minimum UTME score to apply is **180**", ask("What are the admission requirements?").data["reply"]
        )
        self.assertIn("[Apply online](/apply)", ask("how do i apply").data["reply"])
        self.assertIn("/programmes/CSC", ask("Tell me about computer science").data["reply"])
        self.assertIn("/programmes/CSC", ask("Which programmes do you offer?").data["reply"])
        self.assertIn("admissions@", ask("Where is the university located?").data["reply"])

    def test_personal_questions_go_to_the_portal(self):
        self.assertIn("/login/applicant", ask("How can I check my admission status?").data["reply"])

    def test_unknown_questions_get_a_polite_fallback_with_suggestions(self):
        data = ask("What is the capital of France?").data
        self.assertIn("don't have an answer", data["reply"])
        self.assertTrue(data["suggestions"])

    def test_validation(self):
        self.assertEqual(APIClient().post(URL, {"messages": []}, format="json").status_code, 400)
        self.assertEqual(ask("x" * 501).status_code, 400)
        ends_with_reply = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        self.assertEqual(APIClient().post(URL, {"messages": ends_with_reply}, format="json").status_code, 400)
        self.assertEqual(
            APIClient().post(URL, {"messages": [{"role": "system", "content": "x"}]}, format="json").status_code, 400
        )

    @mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"chat": "2/hour"})
    def test_rate_limited(self):
        self.assertEqual([ask("hi").status_code for _ in range(3)], [200, 200, 429])

    def test_suggestions_endpoint(self):
        data = APIClient().get(URL).data
        self.assertFalse(data["ai"])
        self.assertIn("How do I apply?", data["suggestions"])


@override_settings(ANTHROPIC_API_KEY="sk-ant-test", CHATBOT_MODEL="claude-sonnet-5")
class ClaudeTests(TestCase):
    def setUp(self):
        cache.clear()
        make_programme(make_department(), name="Accounting", code="ACC")

    def test_asks_claude_with_the_university_knowledge(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = {"content": [{"type": "text", "text": "Apply at [Apply online](/apply)."}]}
        history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]
        with mock.patch("apps.website.chatbot.requests.post", return_value=response) as post:
            data = ask("How do I apply?", history).data
        self.assertEqual((data["source"], data["reply"]), ("ai", "Apply at [Apply online](/apply)."))
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "claude-sonnet-5")
        self.assertEqual([m["role"] for m in body["messages"]], ["user", "assistant", "user"])
        system = body["system"][0]
        self.assertIn("B.Sc. Accounting", system["text"])
        self.assertIn("Never guess fees", system["text"])
        self.assertEqual(system["cache_control"], {"type": "ephemeral"})
        self.assertEqual(post.call_args.kwargs["headers"]["x-api-key"], "sk-ant-test")

    def test_falls_back_when_the_api_fails(self):
        with mock.patch("apps.website.chatbot.requests.post", side_effect=requests.ConnectionError):
            data = ask("How can I contact the university?").data
        self.assertEqual(data["source"], "faq")
        self.assertIn("info@", data["reply"])
