import streamlit as st
import os
from datetime import datetime
import tempfile
import json
import nest_asyncio
nest_asyncio.apply()

from ai_services import AIServices

from database import DatabaseManager
from utils import FileHandler, display_meeting_results, format_duration

# thats justt page configuration
st.set_page_config(
    page_title="Smart Meeting Assistant - Asistentunia",
    page_icon="👾",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def init_services():
    """Initialize AI services and database"""
    ai_services = AIServices()
    db_manager = DatabaseManager()
    return ai_services, db_manager


ai_services, db_manager = init_services()
file_handler = FileHandler()

def set_page(page_name):
    st.session_state.navigation_choice = page_name


def main():
    st.title("🎯 Smart Meeting Assistant")
    st.markdown("**Transform your meetings into actionable insights using AI**")

    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Choose a page", [
        "📝 Process New Meeting",
        "🔍 Search & Analytics",
        "📊 Meeting Dashboard",
        "📅 Calendar & Tasks",
        "🗑️ Meeting Management"
    ],
    key="navigation_choice"
                                )

    if page == "📝 Process New Meeting":
        process_meeting_page()
    elif page == "🔍 Search & Analytics":
        search_analytics_page()
    elif page == "📊 Meeting Dashboard":
        dashboard_page()
    elif page == "📅 Calendar & Tasks":
        calendar_tasks_page()
    elif page == "🗑️ Meeting Management":
        meeting_management_page()


def process_meeting_page():
    st.header("Process New Meeting")

    # Meeting details
    col1, col2 = st.columns(2)
    with col1:
        meeting_title = st.text_input("Meeting Title*", "Weekly Team Sync")
        meeting_date = st.date_input("Meeting Date", datetime.now())

    with col2:
        language = st.selectbox("Meeting Language", [
            ("auto", "Auto-detect"),
            ("en", "English"),
            ("ka", "Georgian"),
            ("sk", "Slovak"),
            ("sl", "Slovenian"),
            ("lv", "Latvian")
        ], format_func=lambda x: x[1])
        language_code = language[0]

    # File upload with video support
    st.subheader("Upload Meeting Recording")
    uploaded_file = st.file_uploader(
        "Choose audio or video file",
        type=['mp3', 'wav', 'm4a', 'mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv'],
        help="Supports audio files (mp3, wav, m4a) and video files (mp4, mov, avi, mkv, flv, wmv). Video files will be automatically converted to audio."
    )

    if uploaded_file is not None:
        file_size = len(uploaded_file.getvalue()) / (1024 * 1024)  # MB
        file_type = file_handler.get_file_type(uploaded_file.name)

        st.success(f"File uploaded: {uploaded_file.name}")
        st.info(f"File size: {file_size:.2f} MB | Type: {file_type}")

        # Show file type specific information
        if file_type == 'video':
            st.warning("📹 Video file detected - will be converted to audio for processing")
        else:
            st.info("🎵 Audio file ready for processing")

        if st.button("🚀 Process Meeting", type="primary"):
            with st.spinner("Processing meeting... This may take a few minutes."):
                temp_path = None
                audio_path = None

                try:
                    # Step 1: Save uploaded file
                    temp_path = file_handler.save_uploaded_file(uploaded_file)

                    # Step 2: Convert to audio if needed
                    if file_type == 'video':
                        st.write("🎬 Converting video to audio...")
                        audio_path = file_handler.convert_video_to_audio(temp_path)
                        if not audio_path:
                            st.error("Video conversion failed. Please try a different file.")
                            return
                        st.success("✅ Video converted to audio!")
                    else:
                        audio_path = temp_path

                    # Step 3: Transcribe audio
                    st.write("🎵 Transcribing audio...")
                    transcript_data = ai_services.transcribe_audio(
                        audio_path,
                        language_code if language_code != 'auto' else None
                    )

                    if not transcript_data:
                        st.error("Transcription failed. Please check your audio file.")
                        return

                    st.success("✅ Transcription completed!")

                    # Show transcript preview
                    with st.expander("📝 View Transcript Preview"):
                        st.text_area("Transcript",
                                     transcript_data['text'][:1000] + "..." if len(transcript_data['text']) > 1000 else
                                     transcript_data['text'], height=150)

                    # Step 4: Analyze meeting
                    st.write("🧠 Analyzing meeting content...")
                    analysis = ai_services.analyze_meeting(
                        transcript_data['text'],
                        transcript_data.get('language', 'en')
                    )

                    if not analysis:
                        st.error("Meeting analysis failed.")
                        return

                    st.success("✅ Analysis completed!")

                    # Step 5: Generate embeddings for search
                    st.write("🔍 Generating embeddings for search...")
                    embeddings = ai_services.get_embeddings(
                        f"{meeting_title} {analysis.get('summary', '')} {' '.join(analysis.get('decisions', []))}"
                    )

                    # Step 6: Generate visual summary
                    st.write("🎨 Creating visual summary...")
                    visual_url = ai_services.generate_visual_summary(analysis)
                    if visual_url:
                        st.success("✅ Visual summary created!")

                    # Step 7: Process function calls and extract calendar/task data
                    calendar_events = []
                    tasks = []

                    if analysis.get('function_calls'):
                        st.write("📅 Processing calendar events and tasks...")
                        for call in analysis['function_calls']:
                            if call['type'] == 'calendar_event' and call['result'].get('success'):
                                calendar_events.append(call['result']['event'])
                            elif call['type'] == 'task' and call['result'].get('success'):
                                tasks.append(call['result']['task'])

                    # Step 8: Save to database with complete data
                    meeting_data = {
                        'title': meeting_title,
                        'date': str(meeting_date),
                        # 'duration': f"{transcript_data.get('duration', 0):.1f} minutes",
                        'duration': format_duration(transcript_data.get('duration', 0)),  # <--

                        'transcript': transcript_data['text'],  # Save full transcript
                        'summary': analysis.get('summary', ''),
                        'decisions': analysis.get('decisions', []),
                        'action_items': analysis.get('action_items', []),
                        'participants': analysis.get('participants', []),
                        'follow_up': analysis.get('follow_up', []),
                        'visual_summary_url': visual_url,  # Save image URL
                        'language': transcript_data.get('language', 'en'),
                        'embeddings': embeddings,
                        'calendar_events': calendar_events,  # Save calendar events
                        'tasks': tasks,  # Save tasks
                        'function_calls': analysis.get('function_calls', [])  # Save function call log
                    }

                    meeting_id = db_manager.save_meeting(meeting_data)

                    if meeting_id:
                        st.success("✅ Meeting saved to knowledge base!")

                        # Display results with calendar integration
                        display_meeting_results(meeting_data, analysis)

                        # Show calendar events and tasks created
                        display_calendar_integration_results(calendar_events, tasks)

                        # Show similar meetings
                        st.subheader("🔗 Similar Meetings")
                        similar = db_manager.get_similar_meetings(meeting_id)
                        if similar:
                            for sim in similar:
                                st.write(f"📄 **{sim['title']}** (Similarity: {sim['similarity']:.2f})")
                                st.write(f"*{sim['date']}* - {sim['summary'][:100]}...")
                        else:
                            st.info("No similar meetings found yet.")

                except Exception as e:
                    st.error(f"Processing failed: {str(e)}")
                    st.exception(e)  # Show full traceback for debugging

                finally:
                    # Clean up temporary files
                    for path in [temp_path, audio_path]:
                        if path and os.path.exists(path) and path != temp_path:
                            try:
                                os.unlink(path)
                            except:
                                pass
                    if temp_path and os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                        except:
                            pass


def display_calendar_integration_results(calendar_events, tasks):
    """Display created calendar events and tasks"""
    if calendar_events or tasks:
        st.subheader("📅 Calendar Integration Results")

        col1, col2 = st.columns(2)

        with col1:
            if calendar_events:
                st.write("**📅 Calendar Events Created:**")
                for event in calendar_events:
                    st.success(f"✅ **{event['title']}**")
                    st.write(f"📅 {event['date']} at {event['time']}")
                    st.write(f"📝 {event['description']}")
                    st.write("---")
            else:
                st.info("No calendar events were created from this meeting.")

        with col2:
            if tasks:
                st.write("**📝 Tasks Created:**")
                for task in tasks:
                    priority_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}.get(task['priority'], '🟡')
                    st.success(f"✅ **{task['task']}**")
                    st.write(f"👤 Assigned to: {task['assignee']}")
                    if task.get('deadline'):
                        st.write(f"⏰ Deadline: {task['deadline']}")
                    st.write(f"{priority_emoji} Priority: {task['priority'].title()}")
                    st.write("---")
            else:
                st.info("No tasks were created from this meeting.")


def search_analytics_page():
    st.header("🔍 Search & Analytics")

    # Search interface
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("Search meetings...", placeholder="Enter keywords to search through all meetings")
    with col2:
        max_results = st.number_input("Max Results", min_value=1, max_value=20, value=10)

    if search_query:
        with st.spinner("Searching meetings..."):
            # search_query = AIServices.translate_text(search_query, 'en', ai_services)
            ai_service_self = AIServices()
            translated_search_query = ai_service_self.translate_to_english_if_needed(search_query)
            print(translated_search_query)
            results = db_manager.search_meetings(translated_search_query, max_results)

            if results:
                st.success(f"Found {len(results)} relevant meetings")

                for result in results:
                    with st.expander(
                            f"📄 {result['title']} - {result['date']} (Similarity: {result['similarity']:.2f})"):
                        st.write(f"**Summary:** {result['summary']}")
                        st.write(f"**Transcript Preview:** {result['transcript']}")

                        if st.button(f"View Full Meeting", key=f"view_{result['id']}"):
                            st.session_state.selected_meeting = result['id']
                            st.rerun()
            else:
                st.info("No meetings found matching your search.")

    # Display selected meeting details if any
    if hasattr(st.session_state, 'selected_meeting'):
        meeting = db_manager.get_meeting_by_id(st.session_state.selected_meeting)
        if meeting:
            st.divider()
            st.subheader(f"📄 {meeting['title']}")
            display_full_meeting_details(meeting)


def display_full_meeting_details(meeting, show_transcript_expander=True):
    """Display full meeting details with optional transcript expander"""
    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Date:** {meeting['date']}")
        st.write(f"**Duration:** {meeting.get('duration', 'N/A')}")
        st.write(f"**Language:** {meeting.get('language', 'en').upper()}")

    with col2:
        if meeting.get('visual_summary_url'):
            st.image(meeting['visual_summary_url'], caption="Meeting Visual Summary", width=200)

    # Transcript - conditional expander
    if show_transcript_expander:
        with st.expander("📝 Full Transcript"):
            st.text_area("Transcript", meeting.get('transcript', 'No transcript available'), height=300)
    else:
        # Show transcript directly without expander
        st.subheader("📝 Full Transcript")
        st.text_area("Transcript", meeting.get('transcript', 'No transcript available'), height=300)

    # Summary and analysis
    st.write(f"**Summary:** {meeting.get('summary', 'No summary available')}")

    col1, col2 = st.columns(2)
    with col1:
        st.write("**Decisions:**")
        for decision in meeting.get('decisions', []):
            st.write(f"• {decision}")

    with col2:
        st.write("**Action Items:**")
        for item in meeting.get('action_items', []):
            if isinstance(item, dict):
                st.write(f"• {item.get('task', 'Unknown task')} - {item.get('assignee', 'Unassigned')}")
            else:
                st.write(f"• {item}")


def dashboard_page():
    st.header("📊 Meeting Dashboard")

    # Get statistics
    stats = db_manager.get_meeting_statistics()

    if not stats:
        st.info("No meeting data available yet.")
        return

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Meetings", stats.get('total_meetings', 0))

    with col2:
        st.metric("Recent Meetings (30 days)", stats.get('recent_count', 0))

    with col3:
        st.metric("Calendar Events", stats.get('calendar_events', 0))

    with col4:
        pending_tasks = stats.get('task_stats', {}).get('pending', 0)
        st.metric("Pending Tasks", pending_tasks)

    st.divider()

    # Charts and visualizations
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Language Distribution")
        language_stats = stats.get('language_stats', [])
        if language_stats:
            import pandas as pd
            df = pd.DataFrame(language_stats, columns=['Language', 'Count'])
            st.bar_chart(df.set_index('Language'))
        else:
            st.info("No language data available")

    with col2:
        st.subheader("📋 Task Status")
        task_stats = stats.get('task_stats', {})
        if task_stats:
            import pandas as pd
            df = pd.DataFrame(list(task_stats.items()), columns=['Status', 'Count'])
            st.bar_chart(df.set_index('Status'))
        else:
            st.info("No task data available")

    # Recent meetings
    st.subheader("📅 Recent Meetings")
    meetings = db_manager.get_all_meetings()

    if meetings:
        for meeting in meetings[:5]:  # Show last 5 meetings
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.write(f"**{meeting['title']}**")
                st.write(meeting.get('summary', 'No summary')[:100] + "...")

            with col2:
                st.write(f"📅 {meeting['date']}")
                st.write(f"🕒 {meeting.get('duration', 'N/A')}")

            with col3:
                if st.button(f"View Details", key=f"dashboard_view_{meeting['id']}"):
                    st.session_state.selected_meeting = meeting['id']
                    # st.switch_page("🔍 Search & Analytics") i modified this noe
                    st.button(
                        "Go to Search & Analytics",
                        on_click=set_page,
                        args=("🔍 Search & Analytics",)
                    )
    else:
        st.info("No meetings processed yet.")


def calendar_tasks_page():
    st.header("📅 Calendar & Tasks")

    # Tabs for calendar and tasks
    tab1, tab2 = st.tabs(["📅 Calendar Events", "📝 Tasks"])

    with tab1:
        st.subheader("Upcoming Calendar Events")

        days_ahead = st.slider("Show events for next N days", 1, 30, 7)
        events = db_manager.get_calendar_events(days_ahead)

        if events:
            for event in events:
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])

                    with col1:
                        st.write(f"**{event['title']}**")
                        st.write(f"📝 {event.get('description', 'No description')}")
                        if event.get('meeting_title'):
                            st.caption(f"From meeting: {event['meeting_title']}")

                    with col2:
                        st.write(f"📅 {event['date']}")
                        st.write(f"🕒 {event['time']}")

                    with col3:
                        status_color = {"scheduled": "🟡", "completed": "🟢", "cancelled": "🔴"}.get(event['status'], "⚪")
                        st.write(f"{status_color} {event['status'].title()}")

                    st.divider()
        else:
            st.info(f"No calendar events scheduled for the next {days_ahead} days.")

    with tab2:
        st.subheader("Task Management")

        # Task filters
        col1, col2 = st.columns(2)
        with col1:
            show_status = st.selectbox("Filter by Status", ["all", "pending", "completed", "in_progress"])
        with col2:
            show_priority = st.selectbox("Filter by Priority", ["all", "high", "medium", "low"])

        # Get tasks
        if show_status == "all":
            tasks = db_manager.get_pending_tasks()  # You might want to add a get_all_tasks method
        else:
            tasks = db_manager.get_pending_tasks()  # Filter later

        if tasks:
            for task in tasks:
                # Apply filters
                if show_status != "all" and task['status'] != show_status:
                    continue
                if show_priority != "all" and task['priority'] != show_priority:
                    continue

                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

                    with col1:
                        st.write(f"**{task['task']}**")
                        st.write(f"👤 Assigned to: {task['assignee']}")
                        if task.get('meeting_title'):
                            st.caption(f"From meeting: {task['meeting_title']}")

                    with col2:
                        if task.get('deadline'):
                            st.write(f"⏰ {task['deadline']}")
                        else:
                            st.write("⏰ No deadline")

                    with col3:
                        priority_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}.get(task['priority'], '🟡')
                        st.write(f"{priority_emoji} {task['priority'].title()}")

                    with col4:
                        if task['status'] == 'pending':
                            if st.button(f"Mark Complete", key=f"complete_{task['id']}"):
                                if db_manager.update_task_status(task['id'], 'completed'):
                                    st.success("Task marked as completed!")
                                    st.rerun()

                    st.divider()
        else:
            st.info("No tasks found.")


def meeting_management_page():
    st.header("🗑️ Meeting Management")

    # Get all meetings
    meetings = db_manager.get_all_meetings()

    if not meetings:
        st.info("No meetings to manage.")
        return

    st.subheader("All Meetings")

    # Add search/filter options
    col1, col2 = st.columns(2)
    with col1:
        search_filter = st.text_input("Filter by title...")
    with col2:
        sort_by = st.selectbox("Sort by", ["Date (Newest)", "Date (Oldest)", "Title"])

    # Apply filters and sorting
    filtered_meetings = meetings
    if search_filter:
        filtered_meetings = [m for m in meetings if search_filter.lower() in m['title'].lower()]

    if sort_by == "Date (Oldest)":
        filtered_meetings.sort(key=lambda x: x['created_at'])
    elif sort_by == "Title":
        filtered_meetings.sort(key=lambda x: x['title'])

    # Display meetings with management options
    for meeting in filtered_meetings:
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.write(f"**{meeting['title']}**")
                st.write(f"📅 {meeting['date']} | 🕒 {meeting.get('duration', 'N/A')}")
                st.write(meeting.get('summary', 'No summary')[:150] + "...")

            with col2:
                if st.button(f"View Details", key=f"mgmt_view_{meeting['id']}"):
                    st.session_state.selected_meeting = meeting['id']
                    st.session_state.show_details = True

            with col3:
                if st.button(f"🗑️ Delete", key=f"delete_{meeting['id']}", type="secondary"):
                    st.session_state[f"confirm_delete_{meeting['id']}"] = True

                # Confirmation dialog
                if st.session_state.get(f"confirm_delete_{meeting['id']}", False):
                    st.warning("Are you sure? This action cannot be undone.")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("Yes, Delete", key=f"confirm_yes_{meeting['id']}", type="primary"):
                            if db_manager.delete_meeting(meeting['id']):
                                st.success("Meeting deleted successfully!")
                                del st.session_state[f"confirm_delete_{meeting['id']}"]
                                st.rerun()
                            else:
                                st.error("Failed to delete meeting.")
                    with col_no:
                        if st.button("Cancel", key=f"confirm_no_{meeting['id']}"):
                            del st.session_state[f"confirm_delete_{meeting['id']}"]
                            st.rerun()

            st.divider()

    # Show selected meeting details OUTSIDE the loop to avoid nesting
    if st.session_state.get('show_details') and st.session_state.get('selected_meeting'):
        st.divider()
        full_meeting = db_manager.get_meeting_by_id(st.session_state.selected_meeting)
        if full_meeting:
            st.subheader(f"📄 Meeting Details: {full_meeting['title']}")
            # Don't use expander for transcript since we're showing details directly
            display_full_meeting_details(full_meeting, show_transcript_expander=False)

            # Add close button
            if st.button("Close Details"):
                st.session_state.show_details = False
                st.session_state.selected_meeting = None
                st.rerun()


if __name__ == "__main__":
    main()