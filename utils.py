import os
import tempfile
import hashlib
import subprocess
import streamlit as st
from typing import Dict, Any, Optional, List
import platform
from datetime import datetime, timedelta
import json


class FileHandler:

    def __init__(self):
        self.video_extensions = ['mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'webm', 'm4v']
        self.audio_extensions = ['mp3', 'wav', 'm4a', 'flac', 'ogg', 'aac', 'wma']

    def get_file_type(self, filename: str) -> str:
        extension = filename.lower().split('.')[-1]
        if extension in self.video_extensions:
            return 'video'
        elif extension in self.audio_extensions:
            return 'audio'
        else:
            return 'unknown'

    def get_file_hash(self, file_content: bytes) -> str:
        # hashing file content to avoid duplicate processingg
        return hashlib.md5(file_content).hexdigest()

    def save_uploaded_file(self, uploaded_file) -> Optional[str]:
        try:
            file_extension = uploaded_file.name.split('.')[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                return tmp_file.name
        except Exception as e:
            st.error(f"Error saving file: {str(e)}")
            return None

    def convert_video_to_audio(self, video_path: str) -> Optional[str]:
        try:
            if not self._check_ffmpeg():
                st.error("FFmpeg is not installed. Please install FFmpeg to process video files.")
                st.info("Install FFmpeg: https://ffmpeg.org/download.html")
                return None

            audio_path = video_path.rsplit('.', 1)[0] + '_audio.wav'

            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # no video
                '-acodec', 'pcm_s16le',  # uncompressed WAV
                '-ar', '16000',  # 16kHz sample rate for speech
                '-ac', '1',  # mono
                '-y',  # overwrite output file
                audio_path
            ]

            with st.spinner("Converting video to audio..."):
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

            if process.returncode == 0:
                return audio_path
            else:
                st.error(f"FFmpeg conversion failed: {process.stderr}")
                return None

        except subprocess.TimeoutExpired:
            st.error("Video conversion timed out. Please try a smaller file.")
            return None
        except Exception as e:
            st.error(f"Video conversion error: {str(e)}")
            return None

    def _check_ffmpeg(self) -> bool:
        try:
            subprocess.run(['ffmpeg', '-version'],
                         capture_output=True,
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        try:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            file_ext = file_name.split('.')[-1].lower()

            return {
                'name': file_name,
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'extension': file_ext,
                'type': self.get_file_type(file_name),
                'path': file_path
            }
        except Exception as e:
            return {
                'name': 'Unknown',
                'size': 0,
                'size_mb': 0,
                'extension': 'unknown',
                'type': 'unknown',
                'error': str(e)
            }


def display_meeting_results(meeting_data: Dict[str, Any], analysis: Dict[str, Any]):

    st.subheader("📋 Executive Summary")
    summary = analysis.get('summary', 'No summary available')
    st.write(summary)


    if meeting_data.get('visual_summary_url'):
        st.subheader("🎨 Visual Summary")
        try:
            st.image(meeting_data['visual_summary_url'],
                     caption="AI-Generated Meeting Visual Summary",
                     use_container_width=True)
        except Exception as e:
            st.warning(f"Could not display visual summary: {str(e)}")
    col1, col2 = st.columns(2)

    with col1:

        st.subheader("✅ Key Decisions")
        decisions = analysis.get('decisions', [])
        if decisions:
            for i, decision in enumerate(decisions, 1):
                st.write(f"{i}. {decision}")
        else:
            st.write("No key decisions identified")


        participants = analysis.get('participants', [])
        if participants:
            st.subheader("👥 Participants")
            for participant in participants:
                st.write(f"• {participant}")

    with col2:

        st.subheader("📝 Action Items")
        action_items = analysis.get('action_items', [])
        if action_items:
            for i, item in enumerate(action_items):
                if isinstance(item, dict):
                    priority = item.get('priority', 'medium').title()
                    priority_emoji = {'Low': '🟢', 'Medium': '🟡', 'High': '🔴'}.get(priority, '🟡')

                    st.write(f"{priority_emoji} **{item.get('task', 'Unknown task')}**")
                    st.write(f"👤 **Assignee:** {item.get('assignee', 'Unassigned')}")
                    st.write(f"📅 **Deadline:** {item.get('deadline', 'Not specified')}")
                    st.write(f"⚡ **Priority:** {priority}")
                    st.write("---")
                else:
                    st.write(f"• {item}")
        else:
            st.write("No action items identified")

    # Follow-up items
    follow_up = analysis.get('follow_up', [])
    if follow_up:
        st.subheader("🔄 Follow-up Required")
        for item in follow_up:
            st.write(f"• {item}")

    # Function calls and automation results
    display_automation_results(analysis)

    # Calendar and task integration display
    display_calendar_and_tasks(analysis, meeting_data)


def display_automation_results(analysis: Dict[str, Any]):
    """Display automated actions and function call results"""
    function_calls = analysis.get('function_calls', [])
    if function_calls:
        st.subheader("🤖 Automated Actions")

        success_count = sum(1 for call in function_calls if call.get('result', {}).get('success', False))
        total_count = len(function_calls)

        st.info(f"Successfully executed {success_count}/{total_count} automated actions")

        for call in function_calls:
            result = call.get('result', {})
            success = result.get('success', False)

            icon = "✅" if success else "❌"
            function_name = call.get('function', 'Unknown Function')

            with st.expander(f"{icon} {function_name.replace('_', ' ').title()}", expanded=success):
                if success:
                    st.success(result.get('message', 'Action completed successfully'))

                    # Display created items
                    if 'event' in result:
                        display_created_event(result['event'])
                    elif 'task' in result:
                        display_created_task(result['task'])
                else:
                    st.error(f"Failed: {result.get('error', 'Unknown error')}")

                # Show function arguments directly without nested expander
                st.subheader("Function Arguments:")
                st.json(call.get('arguments', {}))


def display_created_event(event: Dict[str, Any]):
    """Display details of a created calendar event"""
    st.write("📅 **Calendar Event Created:**")
    st.write(f"**Title:** {event.get('title', 'Untitled')}")
    st.write(f"**Date:** {event.get('date', 'TBD')}")
    st.write(f"**Time:** {event.get('time', 'TBD')}")
    if event.get('description'):
        st.write(f"**Description:** {event.get('description')}")


def display_created_task(task: Dict[str, Any]):
    """Display details of a created task"""
    st.write("✅ **Task Created:**")
    st.write(f"**Task:** {task.get('task', 'Untitled')}")
    st.write(f"**Assignee:** {task.get('assignee', 'Unassigned')}")
    st.write(f"**Priority:** {task.get('priority', 'medium').title()}")
    if task.get('deadline'):
        st.write(f"**Deadline:** {task.get('deadline')}")


def display_calendar_and_tasks(analysis: Dict[str, Any], meeting_data: Dict[str, Any]):
    """Display calendar events and tasks created from the meeting"""
    
    # Calendar Events Section
    calendar_events = analysis.get('calendar_events', []) or meeting_data.get('calendar_events', [])
    tasks = analysis.get('tasks', []) or meeting_data.get('tasks', [])
    
    if calendar_events or tasks:
        st.subheader("📋 Generated Schedule Items")
        
        cal_col, task_col = st.columns(2)
        
        with cal_col:
            if calendar_events:
                st.write("📅 **Calendar Events:**")
                for event in calendar_events:
                    with st.container():
                        st.write(f"**{event.get('title', 'Untitled Event')}**")
                        st.write(f"📅 {event.get('date', 'TBD')} at {event.get('time', 'TBD')}")
                        if event.get('description'):
                            st.write(f"📝 {event.get('description')}")
                        st.write("---")
            else:
                st.write("📅 No calendar events created")
        
        with task_col:
            if tasks:
                st.write("✅ **Tasks Created:**")
                for task in tasks:
                    priority_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}.get(
                        task.get('priority', 'medium').lower(), '🟡'
                    )
                    
                    with st.container():
                        st.write(f"{priority_emoji} **{task.get('task', 'Untitled Task')}**")
                        st.write(f"👤 {task.get('assignee', 'Unassigned')}")
                        if task.get('deadline'):
                            st.write(f"📅 Due: {task.get('deadline')}")
                        st.write("---")
            else:
                st.write("✅ No tasks created")


def display_meeting_transcript(transcript: str, max_length: int = 1000):
    """Display meeting transcript with expansion option"""
    if not transcript:
        st.write("No transcript available")
        return
    
    st.subheader("📝 Meeting Transcript")
    
    if len(transcript) <= max_length:
        st.text_area("Full Transcript", transcript, height=300, disabled=True)
    else:
        # Show preview with expand option
        preview = transcript[:max_length] + "..."
        st.text_area("Transcript Preview", preview, height=200, disabled=True)
        
        if st.button("Show Full Transcript"):
            st.text_area("Full Transcript", transcript, height=500, disabled=True)


def display_upcoming_calendar_events(events: List[Dict[str, Any]]):
    """Display upcoming calendar events"""
    if not events:
        st.info("No upcoming calendar events")
        return
    
    st.subheader("📅 Upcoming Calendar Events")
    
    for event in events:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"**{event.get('title', 'Untitled Event')}**")
                if event.get('description'):
                    st.caption(event.get('description'))
            
            with col2:
                st.write(f"📅 {event.get('date', 'TBD')}")
                st.write(f"🕐 {event.get('time', 'TBD')}")
            
            with col3:
                status = event.get('status', 'scheduled')
                status_emoji = {'scheduled': '⏰', 'completed': '✅', 'cancelled': '❌'}.get(status, '⏰')
                st.write(f"{status_emoji} {status.title()}")
            
            st.write("---")


def display_pending_tasks(tasks: List[Dict[str, Any]]):
    """Display pending tasks with management options"""
    if not tasks:
        st.info("No pending tasks")
        return
    
    st.subheader("✅ Pending Tasks")
    
    for i, task in enumerate(tasks):
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            
            with col1:
                priority = task.get('priority', 'medium').lower()
                priority_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}.get(priority, '🟡')
                st.write(f"{priority_emoji} **{task.get('task', 'Untitled Task')}**")
                if task.get('meeting_title'):
                    st.caption(f"From: {task.get('meeting_title')}")
            
            with col2:
                st.write(f"👤 {task.get('assignee', 'Unassigned')}")
                if task.get('deadline'):
                    deadline = task.get('deadline')
                    if deadline != 'Not specified':
                        try:
                            deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
                            days_left = (deadline_date - datetime.now()).days
                            if days_left < 0:
                                st.write(f"🔴 Overdue by {abs(days_left)} days")
                            elif days_left == 0:
                                st.write("🟡 Due today")
                            else:
                                st.write(f"📅 Due in {days_left} days")
                        except:
                            st.write(f"📅 {deadline}")
            
            with col3:
                st.write(f"⚡ {priority.title()}")
            
            with col4:
                task_id = task.get('id')
                if task_id and st.button("Complete", key=f"complete_{task_id}_{i}"):
                    return task_id  # Return task ID to be handled by main app
            
            st.write("---")
    
    return None


def format_duration(seconds: float) -> str:
    """Format duration in a human-readable way"""
    if seconds is None:
        return "N/A"

    if seconds >= 3600:
        hours = seconds / 3600
        return f"{hours:.1f} hours"
    elif seconds >= 60:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        return f"{seconds:.1f} seconds"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def validate_file_size(file_size_bytes: int, max_size_mb: int = 100) -> bool:
    """Validate if file size is within limits"""
    max_size_bytes = max_size_mb * 1024 * 1024
    return file_size_bytes <= max_size_bytes


def get_system_info() -> Dict[str, str]:
    """Get system information for debugging"""
    return {
        'platform': platform.system(),
        'python_version': platform.python_version(),
        'ffmpeg_available': FileHandler()._check_ffmpeg()
    }


def display_meeting_statistics(stats: Dict[str, Any]):
    """Display comprehensive meeting statistics"""
    if not stats:
        st.info("No statistics available")
        return
    
    st.subheader("📊 Meeting Statistics")
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Meetings", stats.get('total_meetings', 0))
    
    with col2:
        st.metric("Recent Meetings (30 days)", stats.get('recent_count', 0))
    
    with col3:
        st.metric("Calendar Events", stats.get('calendar_events', 0))
    
    with col4:
        task_stats = stats.get('task_stats', {})
        total_tasks = sum(task_stats.values()) if task_stats else 0
        st.metric("Total Tasks", total_tasks)
    
    # Language distribution
    language_stats = stats.get('language_stats', [])
    if language_stats:
        st.subheader("🌍 Language Distribution")
        for lang, count in language_stats:
            lang_name = {'en': 'English', 'ka': 'Georgian', 'auto': 'Auto-detected'}.get(lang, lang)
            st.write(f"• {lang_name}: {count} meetings")
    
    # Task status breakdown
    if task_stats:
        st.subheader("✅ Task Status Breakdown")
        for status, count in task_stats.items():
            status_emoji = {'pending': '⏳', 'completed': '✅', 'cancelled': '❌'}.get(status, '📋')
            st.write(f"{status_emoji} {status.title()}: {count}")


def create_meeting_export(meeting_data: Dict[str, Any]) -> str:
    """Create exportable meeting summary"""
    try:
        export_data = {
            'meeting_title': meeting_data.get('title', 'Untitled Meeting'),
            'date': meeting_data.get('date', 'Unknown Date'),
            'duration': meeting_data.get('duration', 'Unknown'),
            'summary': meeting_data.get('summary', ''),
            'decisions': meeting_data.get('decisions', []),
            'action_items': meeting_data.get('action_items', []),
            'participants': meeting_data.get('participants', []),
            'follow_up': meeting_data.get('follow_up', []),
            'calendar_events': meeting_data.get('calendar_events', []),
            'tasks': meeting_data.get('tasks', []),
            'transcript': meeting_data.get('transcript', ''),
            'export_date': datetime.now().isoformat()
        }
        
        return json.dumps(export_data, indent=2, ensure_ascii=False)
    
    except Exception as e:
        st.error(f"Export error: {str(e)}")
        return ""


def display_similar_meetings(similar_meetings: List[Dict[str, Any]]):
    """Display similar meetings based on content similarity"""
    if not similar_meetings:
        st.info("No similar meetings found")
        return
    
    st.subheader("🔗 Similar Meetings")
    
    for meeting in similar_meetings:
        similarity_score = meeting.get('similarity', 0)
        similarity_percentage = int(similarity_score * 100)
        
        with st.expander(f"📋 {meeting.get('title', 'Untitled')} ({similarity_percentage}% similar)"):
            st.write(f"**Date:** {meeting.get('date', 'Unknown')}")
            st.write(f"**Summary:** {meeting.get('summary', 'No summary available')}")
            
            if st.button(f"View Meeting", key=f"similar_{meeting.get('id')}"):
                st.session_state['selected_meeting_id'] = meeting.get('id')
                st.experimental_rerun()
