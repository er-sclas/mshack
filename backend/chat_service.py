"""
Chat Service for LLM-based Traffic Analysis

This module provides:
- Groq LLM integration for simulation analysis
- Whisper speech-to-text via Groq
- ElevenLabs text-to-speech
"""

import os
import re
import json
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime


class ChatService:
    """Service for LLM chat and voice features."""

    def __init__(
        self,
        groq_api_key: Optional[str] = None,
        elevenlabs_api_key: Optional[str] = None,
    ):
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.elevenlabs_api_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
        self.groq_base_url = "https://api.groq.com/openai/v1"
        self.elevenlabs_base_url = "https://api.elevenlabs.io/v1"

        # Default voice ID for ElevenLabs (Rachel - clear, professional)
        self.default_voice_id = "21m00Tcm4TlvDq8ikWAM"

    def _clean_text_for_tts(self, text: str) -> str:
        """Remove markdown and special symbols for clean TTS output."""
        # Remove markdown bold/italic
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        # Remove markdown headers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Remove markdown links [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove markdown code blocks
        text = re.sub(r'```[^`]*```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Remove pipe characters (tables)
        text = text.replace('|', ',')
        # Remove bullet point markers
        text = re.sub(r'^[-*+]\s+', '', text, flags=re.MULTILINE)
        # Remove numbered list markers but keep the text
        text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
        # Remove special characters that sound bad in TTS
        text = text.replace('—', ', ')
        text = text.replace('–', ', ')
        text = text.replace('≈', 'approximately ')
        text = text.replace('%', ' percent')
        text = text.replace('&', ' and ')
        # Clean up multiple spaces and newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()

    def _format_timeseries_data(self, timeseries: List[Dict]) -> str:
        """Format timeseries data in a compact, readable format."""
        if not timeseries:
            return "No timeseries data available."

        lines = ["TIMESERIES DATA (time, speed m/s, queue, delay s, waiting s):"]
        for i, point in enumerate(timeseries[:15]):  # Limit to 15 data points
            time_val = point.get("timestamp") or point.get("time") or point.get("step", i)
            speed = point.get("avgSpeed") or point.get("speed", "N/A")
            queue = point.get("queueLength") or point.get("queue", "N/A")
            delay = point.get("totalDelay") or point.get("delay", "N/A")
            waiting = point.get("waitingTime") or point.get("waiting", "N/A")

            # Format numbers
            if isinstance(speed, (int, float)):
                speed = f"{speed:.2f}"
            if isinstance(queue, (int, float)):
                queue = f"{queue:.1f}"
            if isinstance(delay, (int, float)):
                delay = f"{delay:.1f}"
            if isinstance(waiting, (int, float)):
                waiting = f"{waiting:.1f}"

            lines.append(f"  {time_val}: speed={speed}, queue={queue}, delay={delay}, wait={waiting}")

        if len(timeseries) > 15:
            lines.append(f"  ... and {len(timeseries) - 15} more data points")

        return "\n".join(lines)

    def _format_run_data(self, run_data: Dict) -> str:
        """Format run data with actual values for LLM context."""
        parts = []

        # Extract run metadata
        if "run" in run_data:
            run = run_data["run"]
            parts.append(f"Run ID: {run.get('id', 'N/A')}")
            parts.append(f"Scenario: {run.get('scenarioId', 'N/A')}")
            parts.append(f"Status: {run.get('status', 'N/A')}")

            # Extract summary metrics if available
            if "summary" in run and run["summary"]:
                s = run["summary"]
                parts.append("\nSUMMARY METRICS:")
                for key, val in s.items():
                    if val is not None:
                        if isinstance(val, float):
                            parts.append(f"  {key}: {val:.2f}")
                        else:
                            parts.append(f"  {key}: {val}")

        # Include actual timeseries data
        if "timeseries_sample" in run_data and run_data["timeseries_sample"]:
            parts.append("")
            parts.append(self._format_timeseries_data(run_data["timeseries_sample"]))
            parts.append(f"\nTotal data points in run: {run_data.get('total_data_points', len(run_data['timeseries_sample']))}")

        return "\n".join(parts) if parts else "No simulation data available"

    def _build_system_prompt(self, run_data: Optional[Dict] = None) -> str:
        """Build the system prompt with context about the simulation."""
        base_prompt = """You are an expert traffic simulation analyst for FlowState, a smart traffic management system in Chennai, India.

IMPORTANT: Your responses will be converted to speech. Write in plain text without any markdown formatting, tables, or special symbols. Do not use asterisks, pipes, dashes for bullets, or other formatting characters. Write naturally as if speaking.

The system covers three key areas:
1. University of Madras with high pedestrian and vehicle traffic during class hours
2. MA Chidambaram Stadium with massive event-driven traffic spikes during cricket matches
3. Anna Salai Junction, one of Chennai's busiest intersections

Key metrics you analyze:
- Average Speed in meters per second, where higher is better indicating smoother flow
- Queue Length as number of waiting vehicles, where lower is better
- Total Delay in seconds as cumulative waiting time, where lower is better
- Waiting Time as time vehicles spend stationary

The ML adaptive control system uses real-time traffic data to dynamically adjust signal timing, predicts congestion 5 minutes ahead using historical patterns, automatically extends green phases for congested approaches, and reduces overall delay by 15 to 30 percent compared to fixed timing.

When analyzing data, reference the specific numbers provided. Be concise and clear."""

        if run_data:
            context = f"\n\nCURRENT SIMULATION DATA:\n{self._format_run_data(run_data)}"
            return base_prompt + context

        return base_prompt

    async def chat(
        self,
        message: str,
        run_data: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> str:
        """
        Send a chat message to Groq LLM and get a response.

        Args:
            message: User's message
            run_data: Optional simulation data for context
            conversation_history: Previous messages in the conversation

        Returns:
            LLM response text (cleaned for TTS)
        """
        if not self.groq_api_key:
            return "Error: Groq API key not configured. Please set GROQ_API_KEY environment variable."

        messages = [
            {"role": "system", "content": self._build_system_prompt(run_data)}
        ]

        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history[-5:])  # Keep last 5 messages to save tokens

        # Add current message
        messages.append({"role": "user", "content": message})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.groq_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "openai/gpt-oss-120b",
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 1024,
                    },
                )

                if response.status_code != 200:
                    error_detail = response.text
                    return f"Error from Groq API: {response.status_code} - {error_detail}"

                data = response.json()
                raw_response = data["choices"][0]["message"]["content"]
                # Clean the response for TTS compatibility
                return self._clean_text_for_tts(raw_response)

        except httpx.TimeoutException:
            return "Error: Request timed out. Please try again."
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"

    async def transcribe_audio(self, audio_data: bytes, filename: str = "audio.webm") -> str:
        """
        Transcribe audio to text using Whisper on Groq.

        Args:
            audio_data: Raw audio bytes
            filename: Original filename for format detection

        Returns:
            Transcribed text
        """
        if not self.groq_api_key:
            print("Transcription error: No Groq API key")
            return "Error: Groq API key not configured."

        if not audio_data or len(audio_data) == 0:
            print("Transcription error: No audio data")
            return "Error: No audio data received."

        print(f"Transcription request: filename={filename}, size={len(audio_data)} bytes")

        # Determine content type from filename
        content_type = "audio/webm"
        if filename.endswith(".mp3"):
            content_type = "audio/mpeg"
        elif filename.endswith(".wav"):
            content_type = "audio/wav"
        elif filename.endswith(".ogg"):
            content_type = "audio/ogg"
        elif filename.endswith(".m4a"):
            content_type = "audio/m4a"
        elif filename.endswith(".mp4"):
            content_type = "audio/mp4"

        print(f"Using content type: {content_type}")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Groq's Whisper endpoint - use proper multipart form
                files = {
                    "file": (filename, audio_data, content_type),
                }
                data = {
                    "model": "whisper-large-v3-turbo",
                    "response_format": "json",
                }

                print(f"Sending to Groq Whisper API...")
                response = await client.post(
                    f"{self.groq_base_url}/audio/transcriptions",
                    headers={
                        "Authorization": f"Bearer {self.groq_api_key}",
                    },
                    files=files,
                    data=data,
                )

                print(f"Groq response status: {response.status_code}")

                if response.status_code != 200:
                    error_text = response.text
                    print(f"Groq Whisper error: {response.status_code} - {error_text}")
                    return f"Transcription error: {response.status_code} - {error_text[:100]}"

                result = response.json()
                text = result.get("text", "")
                print(f"Transcription result: '{text}'")
                return text

        except httpx.TimeoutException:
            print("Transcription timeout")
            return "Error: Transcription timed out. Please try again with a shorter recording."
        except Exception as e:
            print(f"Transcription exception: {str(e)}")
            return f"Error transcribing audio: {str(e)}"

    async def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Convert text to speech using ElevenLabs.

        Args:
            text: Text to convert to speech
            voice_id: Optional ElevenLabs voice ID

        Returns:
            Audio bytes (mp3 format) or None on error
        """
        if not self.elevenlabs_api_key:
            return None

        voice = voice_id or self.default_voice_id

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.elevenlabs_base_url}/text-to-speech/{voice}",
                    headers={
                        "xi-api-key": self.elevenlabs_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": text,
                        "model_id": "eleven_turbo_v2",
                        "voice_settings": {
                            "stability": 0.5,
                            "similarity_boost": 0.75,
                        },
                    },
                )

                if response.status_code != 200:
                    print(f"TTS error: {response.status_code} - {response.text}")
                    return None

                return response.content

        except Exception as e:
            print(f"Error generating speech: {str(e)}")
            return None

    async def analyze_simulation(
        self,
        run_summary: Dict,
        timeseries_data: List[Dict],
        comparison_data: Optional[List[Dict]] = None,
    ) -> str:
        """
        Generate a comprehensive analysis of simulation results.

        Args:
            run_summary: Summary metrics from the run
            timeseries_data: Time-series data points
            comparison_data: Optional data from other runs for comparison

        Returns:
            Analysis text from LLM
        """
        # Build context with actual data
        context = {
            "summary": run_summary,
            "timeseries_sample": timeseries_data[:10] if timeseries_data else [],
            "data_points": len(timeseries_data),
        }

        if comparison_data:
            context["comparison"] = comparison_data

        prompt = """Based on the simulation data provided, please give a comprehensive analysis that covers:

1. **Overall Performance**: How did the simulation perform in terms of average speed, delays, and queue lengths?

2. **Traffic Patterns**: What patterns do you observe in the time-series data? Any notable congestion periods?

3. **ML Adaptive Control Impact**: If adaptive control was enabled, explain how it improved traffic flow compared to fixed timing.

4. **Key Insights**: What are the most important takeaways from this simulation?

5. **Recommendations**: Based on the data, what improvements could be made to the traffic management strategy?

Please be specific and reference actual numbers from the data."""

        return await self.chat(prompt, run_data=context)


# Singleton instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create the chat service singleton."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
