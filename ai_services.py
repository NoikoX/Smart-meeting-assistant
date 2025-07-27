import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI
from googletrans import Translator
import streamlit as st
from datetime import datetime, timedelta
import requests
import base64
import asyncio

from watchfiles import awatch


class CalendarIntegration:

    def __init__(self):
        self.calendar_events = []  # this is just for inmemory storage for demo
        self.tasks = []

    def create_calendar_event(self, title: str, date: str, time: str, description: str = "") -> Dict[str, Any]:
        try:
            #parsing date and time here
            event_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")

            event = {
                "id": len(self.calendar_events) + 1,
                "title": title,
                "date": date,
                "time": time,
                "datetime": event_datetime.isoformat(),
                "description": description,
                "created_at": datetime.now().isoformat(),
                "status": "scheduled"
            }

            self.calendar_events.append(event)
            return {"success": True, "event": event,
                    "message": f"Calendar event '{title}' created for {date} at {time}"}

        except ValueError as e:
            return {"success": False, "error": f"Invalid date/time format: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Calendar creation failed: {str(e)}"}

    def create_task(self, task: str, assignee: str, deadline: str = None, priority: str = "medium") -> Dict[str, Any]:
        try:
            task_item = {
                "id": len(self.tasks) + 1,
                "task": task,
                "assignee": assignee,
                "deadline": deadline,
                "priority": priority,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }

            self.tasks.append(task_item)
            return {"success": True, "task": task_item, "message": f"Task '{task}' assigned to {assignee}"}

        except Exception as e:
            return {"success": False, "error": f"Task creation failed: {str(e)}"}

    def get_upcoming_events(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        cutoff_date = datetime.now() + timedelta(days=days_ahead)
        upcoming = []

        for event in self.calendar_events:
            event_date = datetime.fromisoformat(event["datetime"])
            if event_date > datetime.now() and event_date <= cutoff_date:
                upcoming.append(event)

        return sorted(upcoming, key=lambda x: x["datetime"])

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        return [task for task in self.tasks if task["status"] == "pending"]


class AIServices:
    def __init__(self):
        self.client = self._init_openai_client()
        self.translator = Translator()
        self.calendar = CalendarIntegration()

    @st.cache_data
    def translate_to_english_if_needed(_self, text: str) -> str:
        # this detects the langauge of the input text if its not in english
        try:
            async def _detect_lang_async():
                return await _self.translator.detect(text)

            detected_lang_obj = asyncio.run(_detect_lang_async())
            source_language = detected_lang_obj.lang

            if source_language == 'en':
                # easily if its already in english perfect :DD
                return text
            else:
                async def _translate_async():
                    return await _self.translator.translate(text, dest='en')

                translation_result = asyncio.run(_translate_async())
                return translation_result.text

        except Exception as e:
            st.warning(f"Language detection or translation error: {str(e)}")
            return text


    def _init_openai_client(self) -> OpenAI:
        load_dotenv()
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            st.error("OpenAI API key not found in environment variables!")
            st.stop()
        return OpenAI(api_key=api_key)

    @st.cache_data(ttl=3600)
    def transcribe_audio(_self, file_path: str, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            with open(file_path, "rb") as audio_file:
                if language and language != 'auto':
                    transcript = _self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="verbose_json",
                        language=language
                    )
                else:
                    transcript = _self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="verbose_json"
                    )

            return {
                'text': transcript.text,
                'language': transcript.language,
                'duration': transcript.duration,
                'segments': getattr(transcript, 'segments', [])
            }
        except Exception as e:
            st.error(f"Transcription error: {str(e)}")
            return None

    def analyze_meeting(self, transcript: str, language: str = 'en') -> Optional[Dict[str, Any]]:

        functions = [
            {
                "name": "create_calendar_event",
                "description": "Create a calendar event for follow-up meetings, deadlines, or scheduled activities mentioned in the meeting",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string",
                                  "description": "Event title (e.g., 'Follow-up Team Meeting', 'Project Deadline')"},
                        "date": {"type": "string", "description": "Event date in YYYY-MM-DD format"},
                        "time": {"type": "string", "description": "Event time in HH:MM format (24-hour)"},
                        "description": {"type": "string",
                                        "description": "Detailed event description including context from the meeting"}
                    },
                    "required": ["title", "date", "time", "description"]
                }
            },
            {
                "name": "create_task",
                "description": "Create actionable tasks from action items mentioned in the meeting",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Clear, actionable task description"},
                        "assignee": {"type": "string", "description": "Person assigned to complete the task"},
                        "deadline": {"type": "string",
                                     "description": "Task deadline in YYYY-MM-DD format (if mentioned or can be inferred)"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"],
                                     "description": "Task priority based on urgency mentioned in meeting"}
                    },
                    "required": ["task", "assignee", "priority"]
                }
            }
        ]

        system_prompt = f"""
        You are an expert meeting analyst with calendar and task management capabilities. 

        Analyze the meeting transcript and:
        1. Extract key information for structured summary
        2. Identify any meetings, deadlines, or events that should be scheduled
        3. Create actionable tasks from discussion points
        4. Use function calling when you identify specific calendar events or tasks

        IMPORTANT: Only use function calling when you can extract specific, actionable items with clear dates/times or assignees from the transcript.

        Language: {'Georgian' if language == 'ka' else 'English' if language == 'en' else 'Auto-detected language: ' + language}

        Provide a structured JSON response with:
        - summary: Executive summary (2-3 sentences)
        - decisions: Array of key decisions made
        - action_items: Array of action items with task, assignee, deadline, priority
        - participants: Array of identified participants
        - follow_up: Array of follow-up items needed
        - calendar_events: Array of events that should be scheduled
        - tasks_created: Array of tasks created via function calling
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Meeting transcript:\n\n{transcript}"}
                ],
                functions=functions,
                function_call="auto",
                temperature=0.3,
                max_tokens=2000
            )


            function_results = []
            message = response.choices[0].message

            if message.function_call:
                func_name = message.function_call.name
                func_args = json.loads(message.function_call.arguments)

                if func_name == "create_calendar_event":
                    result = self.calendar.create_calendar_event(**func_args)
                    function_results.append({
                        'type': 'calendar_event',
                        'function': func_name,
                        'arguments': func_args,
                        'result': result
                    })
                elif func_name == "create_task":
                    result = self.calendar.create_task(**func_args)
                    function_results.append({
                        'type': 'task',
                        'function': func_name,
                        'arguments': func_args,
                        'result': result
                    })


            content = message.content or ""

            try:

                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    analysis = self._parse_unstructured_analysis(content)
            except json.JSONDecodeError:
                analysis = self._parse_unstructured_analysis(content)

            analysis['function_calls'] = function_results
            analysis['calendar_integration'] = {
                'events_created': len([r for r in function_results if r['type'] == 'calendar_event']),
                'tasks_created': len([r for r in function_results if r['type'] == 'task'])
            }

            return analysis

        except Exception as e:
            st.error(f"Analysis error: {str(e)}")
            return None

    def _parse_unstructured_analysis(self, content: str) -> Dict[str, Any]:

        summary_match = re.search(r'(?:EXECUTIVE SUMMARY|Summary)[:\n]+(.*?)(?=\n\n|\n[A-Z]|$)', content,
                                  re.DOTALL | re.IGNORECASE)
        decisions_match = re.search(r'(?:KEY DECISIONS|Decisions)[:\n]+(.*?)(?=\n\n|\n[A-Z]|$)', content,
                                    re.DOTALL | re.IGNORECASE)
        actions_match = re.search(r'(?:ACTION ITEMS|Action Items)[:\n]+(.*?)(?=\n\n|\n[A-Z]|$)', content,
                                  re.DOTALL | re.IGNORECASE)

        decisions = []
        if decisions_match:
            decisions_text = decisions_match.group(1).strip()
            decisions = [line.strip('•-* ').strip() for line in decisions_text.split('\n') if
                         line.strip() and not line.strip().startswith(('1.', '2.', '3.'))]

        action_items = []
        if actions_match:
            actions_text = actions_match.group(1).strip()
            for line in actions_text.split('\n'):
                if line.strip() and not line.strip().startswith(('1.', '2.', '3.')):
                    action_items.append({
                        'task': line.strip('•-* ').strip(),
                        'assignee': 'Team',
                        'deadline': 'Not specified',
                        'priority': 'medium'
                    })

        return {
            'summary': summary_match.group(1).strip() if summary_match else content[:300] + "..." if len(
                content) > 300 else content,
            'decisions': decisions if decisions else ["Analysis completed - see full content above"],
            'action_items': action_items if action_items else [
                {'task': 'Review meeting analysis', 'assignee': 'Team', 'priority': 'medium',
                 'deadline': 'Not specified'}
            ],
            'participants': ['Multiple participants identified'],
            'follow_up': ['Review and distribute meeting summary'],
            'calendar_events': [],
            'tasks_created': []
        }

    def get_embeddings(self, text: str) -> List[float]:
        try:
            response = self.client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            st.error(f"Embeddings error: {str(e)}")
            return []

    def generate_visual_summary(self, meeting_data: Dict[str, Any]) -> Optional[str]:
        try:
            summary_text = meeting_data.get('summary', 'Business Meeting')
            decisions_count = len(meeting_data.get('decisions', []))
            actions_count = len(meeting_data.get('action_items', []))
            participants_count = len(meeting_data.get('participants', []))

            prompt = f"""
            Create a professional, modern infographic representing a business meeting summary:

            Meeting Context: {summary_text[:150]}
            Visual Elements Needed:
            - {decisions_count} key decisions (show with checkmarks or decision icons)
            - {actions_count} action items (show with task/assignment icons)
            - {participants_count} participants (show with team/people icons)

            Style Requirements:
            - Clean, corporate design with professional color palette (blues, grays, whites, subtle accents)
            - Modern flat design with clear hierarchy and visual flow
            - Include icons for: meetings, decisions, tasks, calendars, team collaboration
            - Make it presentation-ready and suitable for business reports
            - Focus on visual storytelling without text overlays
            - Use infographic-style layout with sections and visual elements
            """

            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1
            )

            return response.data[0].url

        except Exception as e:
            st.error(f"Visual generation error: {str(e)}")
            return None

    @st.cache_data
    def translate_text(_self, text: str, target_language: str) -> str:
        try:
            result = _self.translator.translate(text, dest=target_language)
            return result.text
        except Exception as e:
            st.warning(f"Translation error: {str(e)}")
            return text

    def get_calendar_events(self) -> List[Dict[str, Any]]:
        return self.calendar.get_upcoming_events()

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        return self.calendar.get_pending_tasks()