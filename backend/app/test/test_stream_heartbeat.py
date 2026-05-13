import asyncio
import unittest
from unittest.mock import patch

from app.config import settings
from app.services.proxy_service import ProxyService


class StreamHeartbeatTest(unittest.IsolatedAsyncioTestCase):
    async def test_with_sse_heartbeat_emits_initial_and_periodic_comments(self):
        release = asyncio.Event()

        async def delayed_stream():
            await release.wait()
            yield "data: hello\n\n"

        with patch.object(settings, "STREAM_HEARTBEAT_INTERVAL_SECONDS", 0.01):
            stream = ProxyService._with_sse_heartbeat(delayed_stream())
            first = await anext(stream)
            second = await anext(stream)
            third = await anext(stream)
            release.set()
            payload = await anext(stream)

        self.assertEqual(first, ": keep-alive\n\n")
        self.assertEqual(second, ": keep-alive\n\n")
        self.assertEqual(third, ": keep-alive\n\n")
        self.assertEqual(payload, "data: hello\n\n")

    async def test_build_streaming_response_sets_sse_headers(self):
        async def simple_stream():
            yield "data: ok\n\n"

        response = ProxyService._build_streaming_response(simple_stream(), "req-123")

        self.assertEqual(response.media_type, "text/event-stream")
        self.assertEqual(response.headers["X-Request-ID"], "req-123")
        self.assertEqual(response.headers["X-Accel-Buffering"], "no")
        self.assertIn("no-transform", response.headers["Cache-Control"])


if __name__ == "__main__":
    unittest.main()
