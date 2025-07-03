import sqlite3
import json
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime
import streamlit as st


class DatabaseManager:
    def __init__(self, db_path: str = "meetings.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database with enhanced schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()


                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS meetings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        date TEXT NOT NULL,
                        duration TEXT,
                        transcript TEXT,  -- Store full transcript
                        summary TEXT,
                        decisions TEXT,  -- JSON array
                        action_items TEXT,  -- JSON array
                        participants TEXT,  -- JSON array
                        follow_up TEXT,  -- JSON array
                        visual_summary_url TEXT,  -- Store image URL
                        language TEXT DEFAULT 'en',
                        embeddings BLOB,  -- Store embeddings as blob
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')


                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS calendar_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        meeting_id INTEGER,
                        title TEXT NOT NULL,
                        date TEXT NOT NULL,
                        time TEXT NOT NULL,
                        datetime TEXT NOT NULL,
                        description TEXT,
                        status TEXT DEFAULT 'scheduled',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
                    )
                ''')


                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        meeting_id INTEGER,
                        task TEXT NOT NULL,
                        assignee TEXT NOT NULL,
                        deadline TEXT,
                        priority TEXT DEFAULT 'medium',
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
                    )
                ''')


                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS function_calls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        meeting_id INTEGER,
                        function_name TEXT NOT NULL,
                        arguments TEXT,  -- JSON
                        result TEXT,     -- JSON
                        success BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
                    )
                ''')

                conn.commit()

        except Exception as e:
            st.error(f"Database initialization error: {str(e)}")

    def save_meeting(self, meeting_data: Dict[str, Any]) -> Optional[int]:

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Insert main meeting record
                cursor.execute('''
                    INSERT INTO meetings (
                        title, date, duration, transcript, summary, decisions, 
                        action_items, participants, follow_up, visual_summary_url, 
                        language, embeddings
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    meeting_data['title'],
                    meeting_data['date'],
                    meeting_data.get('duration', ''),
                    meeting_data.get('transcript', ''),  # Store full transcript
                    meeting_data.get('summary', ''),
                    json.dumps(meeting_data.get('decisions', [])),
                    json.dumps(meeting_data.get('action_items', [])),
                    json.dumps(meeting_data.get('participants', [])),
                    json.dumps(meeting_data.get('follow_up', [])),
                    meeting_data.get('visual_summary_url', ''),  # Store image URL
                    meeting_data.get('language', 'en'),
                    self._serialize_embeddings(meeting_data.get('embeddings', []))
                ))

                meeting_id = cursor.lastrowid

                # Save calendar events if any
                calendar_events = meeting_data.get('calendar_events', [])
                for event in calendar_events:
                    cursor.execute('''
                        INSERT INTO calendar_events (
                            meeting_id, title, date, time, datetime, description, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        meeting_id,
                        event.get('title', ''),
                        event.get('date', ''),
                        event.get('time', ''),
                        event.get('datetime', ''),
                        event.get('description', ''),
                        event.get('status', 'scheduled')
                    ))

                # Save tasks if any
                tasks = meeting_data.get('tasks', [])
                for task in tasks:
                    cursor.execute('''
                        INSERT INTO tasks (
                            meeting_id, task, assignee, deadline, priority, status
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        meeting_id,
                        task.get('task', ''),
                        task.get('assignee', ''),
                        task.get('deadline', ''),
                        task.get('priority', 'medium'),
                        task.get('status', 'pending')
                    ))

                # Save function calls log if any
                function_calls = meeting_data.get('function_calls', [])
                for call in function_calls:
                    cursor.execute('''
                        INSERT INTO function_calls (
                            meeting_id, function_name, arguments, result, success
                        ) VALUES (?, ?, ?, ?, ?)
                    ''', (
                        meeting_id,
                        call.get('function', ''),
                        json.dumps(call.get('arguments', {})),
                        json.dumps(call.get('result', {})),
                        call.get('result', {}).get('success', False)
                    ))

                conn.commit()
                return meeting_id

        except Exception as e:
            st.error(f"Error saving meeting: {str(e)}")
            return None

    def get_meeting_by_id(self, meeting_id: int) -> Optional[Dict[str, Any]]:
        """Get complete meeting data including transcript and visual summary"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get main meeting data
                cursor.execute('''
                    SELECT * FROM meetings WHERE id = ?
                ''', (meeting_id,))

                meeting_row = cursor.fetchone()
                if not meeting_row:
                    return None

                # Convert to dict
                columns = [desc[0] for desc in cursor.description]
                meeting = dict(zip(columns, meeting_row))

                # Parse JSON fields
                meeting['decisions'] = json.loads(meeting.get('decisions', '[]'))
                meeting['action_items'] = json.loads(meeting.get('action_items', '[]'))
                meeting['participants'] = json.loads(meeting.get('participants', '[]'))
                meeting['follow_up'] = json.loads(meeting.get('follow_up', '[]'))

                # Get calendar events
                cursor.execute('''
                    SELECT * FROM calendar_events WHERE meeting_id = ?
                ''', (meeting_id,))
                events = cursor.fetchall()
                event_columns = [desc[0] for desc in cursor.description]
                meeting['calendar_events'] = [dict(zip(event_columns, event)) for event in events]

                # Get tasks
                cursor.execute('''
                    SELECT * FROM tasks WHERE meeting_id = ?
                ''', (meeting_id,))
                tasks = cursor.fetchall()
                task_columns = [desc[0] for desc in cursor.description]
                meeting['tasks'] = [dict(zip(task_columns, task)) for task in tasks]

                # Get function calls
                cursor.execute('''
                    SELECT * FROM function_calls WHERE meeting_id = ?
                ''', (meeting_id,))
                calls = cursor.fetchall()
                call_columns = [desc[0] for desc in cursor.description]
                meeting['function_calls'] = []
                for call in calls:
                    call_dict = dict(zip(call_columns, call))
                    call_dict['arguments'] = json.loads(call_dict.get('arguments', '{}'))
                    call_dict['result'] = json.loads(call_dict.get('result', '{}'))
                    meeting['function_calls'].append(call_dict)

                return meeting

        except Exception as e:
            st.error(f"Error retrieving meeting: {str(e)}")
            return None

    def get_all_meetings(self) -> List[Dict[str, Any]]:
        """Get all meetings with basic info"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        id, title, date, duration, summary, 
                        visual_summary_url, language, created_at
                    FROM meetings 
                    ORDER BY created_at DESC
                ''')

                meetings = []
                columns = [desc[0] for desc in cursor.description]
                for row in cursor.fetchall():
                    meeting = dict(zip(columns, row))
                    meetings.append(meeting)

                return meetings

        except Exception as e:
            st.error(f"Error retrieving meetings: {str(e)}")
            return []

    def search_meetings(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Enhanced semantic search with similarity scoring"""
        try:
            from ai_services import AIServices
            ai_services = AIServices()

            # Get query embeddings
            query_embeddings = ai_services.get_embeddings(query)
            if not query_embeddings:
                return []

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, title, date, summary, transcript, embeddings 
                    FROM meetings 
                    WHERE embeddings IS NOT NULL
                ''')

                results = []
                for row in cursor.fetchall():
                    meeting_id, title, date, summary, transcript, embeddings_blob = row

                    if embeddings_blob:
                        meeting_embeddings = self._deserialize_embeddings(embeddings_blob)
                        similarity = self._cosine_similarity(query_embeddings, meeting_embeddings)

                        if similarity > 0.3:  # Threshold for relevance
                            results.append({
                                'id': meeting_id,
                                'title': title,
                                'date': date,
                                'summary': summary,
                                'transcript': transcript[:500] + "..." if len(transcript) > 500 else transcript,
                                'similarity': similarity
                            })

                # Sort by similarity and limit results
                results.sort(key=lambda x: x['similarity'], reverse=True)
                return results[:max_results]

        except Exception as e:
            st.error(f"Search error: {str(e)}")
            return []

    def get_meeting_statistics(self) -> Dict[str, Any]:
        """Get comprehensive meeting statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Total meetings
                cursor.execute('SELECT COUNT(*) FROM meetings')
                total_meetings = cursor.fetchone()[0]

                # Language distribution
                cursor.execute('''
                    SELECT language, COUNT(*) 
                    FROM meetings 
                    GROUP BY language 
                    ORDER BY COUNT(*) DESC
                ''')
                language_stats = cursor.fetchall()

                # Recent activity (last 10 meetings)
                cursor.execute('''
                    SELECT COUNT(*) FROM meetings 
                    WHERE datetime(created_at) >= datetime('now', '-30 days')
                ''')
                recent_count = cursor.fetchone()[0]

                # Calendar events count
                cursor.execute('SELECT COUNT(*) FROM calendar_events')
                events_count = cursor.fetchone()[0]

                # Tasks statistics
                cursor.execute('''
                    SELECT status, COUNT(*) 
                    FROM tasks 
                    GROUP BY status
                ''')
                task_stats = cursor.fetchall()

                return {
                    'total_meetings': total_meetings,
                    'language_stats': language_stats,
                    'recent_count': recent_count,
                    'calendar_events': events_count,
                    'task_stats': dict(task_stats),
                    'function_calls_success': self._get_function_call_stats()
                }

        except Exception as e:
            st.error(f"Statistics error: {str(e)}")
            return {}

    def get_similar_meetings(self, meeting_id: int, max_results: int = 3) -> List[Dict[str, Any]]:
        """Find similar meetings using embeddings"""
        try:
            meeting = self.get_meeting_by_id(meeting_id)
            if not meeting or not meeting.get('embeddings'):
                return []

            meeting_embeddings = self._deserialize_embeddings(meeting['embeddings'])

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, title, date, summary, embeddings 
                    FROM meetings 
                    WHERE id != ? AND embeddings IS NOT NULL
                ''', (meeting_id,))

                results = []
                for row in cursor.fetchall():
                    other_id, title, date, summary, embeddings_blob = row
                    other_embeddings = self._deserialize_embeddings(embeddings_blob)
                    similarity = self._cosine_similarity(meeting_embeddings, other_embeddings)

                    if similarity > 0.2:
                        results.append({
                            'id': other_id,
                            'title': title,
                            'date': date,
                            'summary': summary,
                            'similarity': similarity
                        })

                results.sort(key=lambda x: x['similarity'], reverse=True)
                return results[:max_results]

        except Exception as e:
            st.error(f"Similar meetings error: {str(e)}")
            return []

    def delete_meeting(self, meeting_id: int) -> bool:
        """Delete meeting and all related data"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Delete from all tables (foreign key constraints will handle cascading)
                cursor.execute('DELETE FROM meetings WHERE id = ?', (meeting_id,))

                if cursor.rowcount > 0:
                    conn.commit()
                    return True
                else:
                    return False

        except Exception as e:
            st.error(f"Delete error: {str(e)}")
            return False

    def get_calendar_events(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming calendar events"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ce.*, m.title as meeting_title 
                    FROM calendar_events ce
                    JOIN meetings m ON ce.meeting_id = m.id
                    WHERE date(ce.date) BETWEEN date('now') AND date('now', '+{} days')
                    ORDER BY ce.datetime
                '''.format(days_ahead))

                events = []
                columns = [desc[0] for desc in cursor.description]
                for row in cursor.fetchall():
                    events.append(dict(zip(columns, row)))

                return events

        except Exception as e:
            st.error(f"Calendar events error: {str(e)}")
            return []

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get all pending tasks"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT t.*, m.title as meeting_title 
                    FROM tasks t
                    JOIN meetings m ON t.meeting_id = m.id
                    WHERE t.status = 'pending'
                    ORDER BY 
                        CASE t.priority 
                            WHEN 'high' THEN 1 
                            WHEN 'medium' THEN 2 
                            ELSE 3 
                        END,
                        t.deadline
                ''')

                tasks = []
                columns = [desc[0] for desc in cursor.description]
                for row in cursor.fetchall():
                    tasks.append(dict(zip(columns, row)))

                return tasks

        except Exception as e:
            st.error(f"Pending tasks error: {str(e)}")
            return []

    def update_task_status(self, task_id: int, status: str) -> bool:
        """Update task status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE tasks SET status = ? WHERE id = ?
                ''', (status, task_id))

                if cursor.rowcount > 0:
                    conn.commit()
                    return True
                return False

        except Exception as e:
            st.error(f"Task update error: {str(e)}")
            return False

    def _serialize_embeddings(self, embeddings: List[float]) -> bytes:
        """Serialize embeddings to bytes for storage"""
        if not embeddings:
            return b''
        return np.array(embeddings, dtype=np.float32).tobytes()

    def _deserialize_embeddings(self, embeddings_blob: bytes) -> List[float]:
        """Deserialize embeddings from bytes"""
        if not embeddings_blob:
            return []
        return np.frombuffer(embeddings_blob, dtype=np.float32).tolist()

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)

        except Exception:
            return 0.0

    def _get_function_call_stats(self) -> Dict[str, Any]:
        """Get function call success statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT function_name, success, COUNT(*) 
                    FROM function_calls 
                    GROUP BY function_name, success
                ''')

                stats = {}
                for func_name, success, count in cursor.fetchall():
                    if func_name not in stats:
                        stats[func_name] = {'success': 0, 'failed': 0}

                    if success:
                        stats[func_name]['success'] = count
                    else:
                        stats[func_name]['failed'] = count

                return stats

        except Exception as e:
            return {}