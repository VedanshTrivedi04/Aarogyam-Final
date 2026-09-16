"""
apps/communications/consumers.py — WebSocket consumers for Chat and WebRTC Call signaling.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger('medadhere')


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Real-time text chat between caregiver and patient.

    Protocol (client → server):
      { "type": "message",  "content": "Hello!" }
      { "type": "typing",   "is_typing": true }
      { "type": "read_receipt" }

    Protocol (server → client):
      { "type": "message",       "id": "uuid", "content": "...", "sender_id": "...",
        "sender_name": "...", "created_at": "iso", "is_own": true/false }
      { "type": "typing",        "sender_id": "...", "is_typing": true }
      { "type": "read_receipt",  "reader_id": "..." }
      { "type": "error",         "message": "..." }
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.room_id = str(self.scope['url_route']['kwargs']['room_id'])
        self.group_name = f'chat_{self.room_id}'
        self.user = user

        # Verify user belongs to this room
        room = await self._get_room()
        if room is None:
            await self.close(code=4003)
            return
        self.room = room

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send last 50 messages as history on connect
        messages = await self._get_history()
        await self.send(text_data=json.dumps({
            'type': 'history',
            'messages': messages,
        }))

        # Mark unread messages as read
        await self._mark_read()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get('type')

        if msg_type == 'message':
            content = (data.get('content') or '').strip()
            if not content:
                return
            msg = await self._save_message(content)
            await self.channel_layer.group_send(self.group_name, {
                'type':        'chat_message',
                'id':          str(msg.id),
                'msg_type':    'message',
                'content':     msg.content,
                'sender_id':   str(self.user.id),
                'sender_name': self.user.full_name or self.user.email,
                'created_at':  msg.created_at.isoformat(),
            })

        elif msg_type == 'file':
            # File already saved via REST /upload/ — broadcast the metadata so
            # both parties see it in real time without refreshing history.
            file_url  = data.get('file_url', '')
            file_name = data.get('file_name', '')
            file_size = data.get('file_size')
            mime_type = data.get('mime_type', 'application/octet-stream')
            if not file_url:
                return
            msg = await self._save_file_message(file_url, file_name, file_size, mime_type)
            await self.channel_layer.group_send(self.group_name, {
                'type':        'chat_message',
                'id':          str(msg.id),
                'msg_type':    'file',
                'content':     '',
                'file_url':    file_url,
                'file_name':   file_name,
                'file_size':   file_size,
                'mime_type':   mime_type,
                'sender_id':   str(self.user.id),
                'sender_name': self.user.full_name or self.user.email,
                'created_at':  msg.created_at.isoformat(),
            })

        elif msg_type == 'typing':
            await self.channel_layer.group_send(self.group_name, {
                'type':      'chat_typing',
                'sender_id': str(self.user.id),
                'is_typing': bool(data.get('is_typing', False)),
            })

        elif msg_type == 'read_receipt':
            await self._mark_read()
            await self.channel_layer.group_send(self.group_name, {
                'type':      'chat_read_receipt',
                'reader_id': str(self.user.id),
            })

    # ── Group event handlers ──────────────────────────────────────────────────

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type':        event.get('msg_type', 'message'),
            'id':          event['id'],
            'content':     event.get('content', ''),
            'file_url':    event.get('file_url'),
            'file_name':   event.get('file_name'),
            'file_size':   event.get('file_size'),
            'mime_type':   event.get('mime_type'),
            'sender_id':   event['sender_id'],
            'sender_name': event['sender_name'],
            'created_at':  event['created_at'],
            'is_own':      event['sender_id'] == str(self.user.id),
        }))

    async def chat_typing(self, event):
        if event['sender_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type':      'typing',
                'sender_id': event['sender_id'],
                'is_typing': event['is_typing'],
            }))

    async def chat_read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'type':      'read_receipt',
            'reader_id': event['reader_id'],
        }))

    # ── DB helpers ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_room(self):
        from .models import ChatRoom
        from apps.clinical.models import Patient, Caregiver
        try:
            room = ChatRoom.objects.select_related('caregiver__user', 'patient__user').get(id=self.room_id)
            user_ids = {str(room.caregiver.user_id), str(room.patient.user_id)}
            if str(self.user.id) not in user_ids:
                return None
            return room
        except ChatRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_history(self):
        from .models import Message
        msgs = Message.objects.filter(room_id=self.room_id).select_related('sender').order_by('-created_at')[:50]
        return [
            {
                'type':        m.message_type or 'message',
                'id':          str(m.id),
                'content':     m.content,
                'file_url':    m.file_url,
                'file_name':   m.file_name,
                'file_size':   m.file_size,
                'mime_type':   m.mime_type,
                'sender_id':   str(m.sender_id),
                'sender_name': m.sender.full_name or m.sender.email,
                'created_at':  m.created_at.isoformat(),
                'is_own':      str(m.sender_id) == str(self.user.id),
                'is_read':     m.is_read,
            }
            for m in reversed(list(msgs))
        ]

    @database_sync_to_async
    def _save_message(self, content: str):
        from .models import Message
        return Message.objects.create(
            room_id=self.room_id,
            sender=self.user,
            content=content,
            message_type='text',
        )

    @database_sync_to_async
    def _save_file_message(self, file_url, file_name, file_size, mime_type):
        from .models import Message
        return Message.objects.create(
            room_id      = self.room_id,
            sender       = self.user,
            content      = '',
            message_type = 'file',
            file_url     = file_url,
            file_name    = file_name,
            file_size    = file_size,
            mime_type    = mime_type,
        )

    @database_sync_to_async
    def _mark_read(self):
        from .models import Message
        Message.objects.filter(room_id=self.room_id, is_read=False).exclude(
            sender=self.user
        ).update(is_read=True)


class CallConsumer(AsyncWebsocketConsumer):
    """
    WebRTC signaling relay for caregiver ↔ patient audio/video calls.
    The server never handles media — it only relays offer/answer/ICE between browsers.

    Protocol (client → server):
      { "type": "call_offer",     "sdp": "...",           "to": "<user_id>" }
      { "type": "call_answer",    "sdp": "...",           "to": "<user_id>" }
      { "type": "ice_candidate",  "candidate": {...},     "to": "<user_id>" }
      { "type": "call_end" }
      { "type": "call_ringing" }

    Protocol (server → client):
      All above events are relayed with "from": "<sender_user_id>" added.
      { "type": "call_error", "message": "..." }
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.room_id = str(self.scope['url_route']['kwargs']['room_id'])
        self.group_name = f'call_{self.room_id}'
        self.user = user

        room = await self._get_room()
        if room is None:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Notify the other party that someone joined the call room
        await self.channel_layer.group_send(self.group_name, {
            'type':    'call_relay',
            'payload': {'type': 'peer_joined', 'from': str(self.user.id)},
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_send(self.group_name, {
                'type':    'call_relay',
                'payload': {'type': 'call_end', 'from': str(self.user.id)},
            })
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        allowed = {'call_offer', 'call_answer', 'ice_candidate', 'call_end', 'call_ringing'}
        if data.get('type') not in allowed:
            return

        data['from'] = str(self.user.id)
        await self.channel_layer.group_send(self.group_name, {
            'type':    'call_relay',
            'payload': data,
        })

    async def call_relay(self, event):
        payload = event['payload']
        # Don't relay a message back to the sender (except peer_joined)
        if payload.get('from') == str(self.user.id) and payload.get('type') != 'peer_joined':
            return
        await self.send(text_data=json.dumps(payload))

    @database_sync_to_async
    def _get_room(self):
        from .models import ChatRoom
        try:
            room = ChatRoom.objects.select_related('caregiver__user', 'patient__user').get(id=self.room_id)
            user_ids = {str(room.caregiver.user_id), str(room.patient.user_id)}
            if str(self.user.id) not in user_ids:
                return None
            return room
        except ChatRoom.DoesNotExist:
            return None


class DoctorCallConsumer(AsyncWebsocketConsumer):
    """
    WebRTC signaling relay for doctor ↔ patient voice/video calls, scoped to a
    ConsultationSession (same offer/answer/ICE relay as CallConsumer — video
    vs audio is negotiated entirely client-side in the SDP, so one consumer
    handles both).

    A patient's call_offer is only relayed to the doctor if the doctor is
    both "accepting calls" (DoctorProfile.is_available) and actually online
    right now (DoctorProfile.is_online, set by NotificationConsumer) —
    otherwise the caller gets `call_error` immediately instead of a ring that
    nobody will ever answer.

    Protocol: identical to CallConsumer (call_offer/call_answer/ice_candidate/
    call_end/call_ringing), plus:
      { "type": "call_error", "reason": "doctor_unavailable" }
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.session_id = str(self.scope['url_route']['kwargs']['session_id'])
        self.group_name = f'doctor_call_{self.session_id}'
        self.user = user

        session = await self._get_session()
        if session is None:
            await self.close(code=4003)
            return
        self.session = session

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        peer_info = await self._peer_join_info()
        await self.channel_layer.group_send(self.group_name, {
            'type':    'call_relay',
            'payload': {'type': 'peer_joined', 'from': str(self.user.id), **peer_info},
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_send(self.group_name, {
                'type':    'call_relay',
                'payload': {'type': 'call_end', 'from': str(self.user.id)},
            })
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        allowed = {'call_offer', 'call_answer', 'ice_candidate', 'call_end', 'call_ringing'}
        if data.get('type') not in allowed:
            return

        if data.get('type') == 'call_offer':
            is_doctor = await self._is_doctor()
            if not is_doctor:
                doctor_ready = await self._doctor_is_reachable()
                if not doctor_ready:
                    await self.send(text_data=json.dumps({
                        'type': 'call_error', 'reason': 'doctor_unavailable',
                    }))
                    return

        data['from'] = str(self.user.id)
        await self.channel_layer.group_send(self.group_name, {
            'type':    'call_relay',
            'payload': data,
        })

    async def call_relay(self, event):
        payload = event['payload']
        if payload.get('from') == str(self.user.id) and payload.get('type') != 'peer_joined':
            return
        await self.send(text_data=json.dumps(payload))

    @database_sync_to_async
    def _get_session(self):
        from apps.doctor_portal.models import ConsultationSession
        try:
            session = ConsultationSession.objects.select_related(
                'doctor__user', 'patient__user'
            ).get(id=self.session_id)
            allowed = {str(session.doctor.user_id), str(session.patient.user_id)}
            if str(self.user.id) not in allowed:
                return None
            if session.status not in ('ACCEPTED', 'ACTIVE'):
                return None
            return session
        except ConsultationSession.DoesNotExist:
            return None

    @database_sync_to_async
    def _is_doctor(self):
        return str(self.user.id) == str(self.session.doctor.user_id)

    @database_sync_to_async
    def _peer_join_info(self):
        """Patient details for the doctor's incoming-call panel (or vice versa)."""
        session = self.session
        if str(self.user.id) == str(session.patient.user_id):
            patient = session.patient
            return {
                'patient': {
                    'id':           str(patient.id),
                    'name':         getattr(patient.user, 'full_name', None) or patient.user.email,
                    'patient_code': getattr(patient, 'patient_code', None),
                }
            }
        doctor = session.doctor
        return {
            'doctor': {
                'id':   str(doctor.id),
                'name': getattr(doctor.user, 'full_name', None) or doctor.user.email,
                'specialization': doctor.specialization,
            }
        }

    @database_sync_to_async
    def _doctor_is_reachable(self):
        self.session.doctor.refresh_from_db()
        return self.session.doctor.is_reachable_for_calls()


# ── Per-user notification push channel ──────────────────────────────────────

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Personal notification channel per user.
    Connect: ws://host/ws/notifications/?token=JWT

    Server → client events:
      { "type": "new_message",   "from": "Dr. X", "preview": "Hello…", "session_id": "uuid" }
      { "type": "ping" }
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.user        = user
        self.group_name  = f'user_notif_{user.id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._set_doctor_online(True)

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self._set_doctor_online(False)

    async def receive(self, text_data):
        pass  # client never sends anything to this channel

    @database_sync_to_async
    def _set_doctor_online(self, online: bool):
        """This socket is the doctor's live-presence signal — a doctor is only
        reachable for a new call while it's open, regardless of the
        is_available toggle."""
        from django.utils import timezone
        from apps.doctor_portal.models import DoctorProfile
        DoctorProfile.objects.filter(user_id=self.user.id).update(
            is_online=online, last_seen_at=timezone.now(),
        )

    # ── Incoming group events ─────────────────────────────────────────────────
    async def user_notification(self, event):
        """Forward any notification event to the connected client."""
        await self.send(text_data=json.dumps(event['payload']))


# ── Doctor ↔ Patient real-time chat ─────────────────────────────────────────

class DoctorChatConsumer(AsyncWebsocketConsumer):
    """
    Real-time chat for a doctor ↔ patient consultation session.
    Channel group: doctor_chat_<session_id>

    Protocol (client → server):
      { "type": "message",  "content": "Hello!" }
      { "type": "typing",   "is_typing": true }

    Protocol (server → client):
      { "type": "history",  "messages": [...] }
      { "type": "message",  "id", "content", "sender_id", "sender_name", "created_at", "is_own" }
      { "type": "typing",   "sender_id", "is_typing" }
      { "type": "session_status", "status": "COMPLETED" }
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.session_id = str(self.scope['url_route']['kwargs']['session_id'])
        self.group_name = f'doctor_chat_{self.session_id}'
        self.user = user

        session = await self._get_session()
        if session is None:
            await self.close(code=4003)
            return
        self.session = session

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send chat history on connect
        history = await self._get_history()
        await self.send(text_data=json.dumps({'type': 'history', 'messages': history}))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get('type')

        if msg_type == 'message':
            content = (data.get('content') or '').strip()
            if not content:
                return
            msg = await self._save_message(content)
            sender_name = getattr(self.user, 'full_name', None) or self.user.email
            event = {
                'type':        'doctor_chat_message',
                'id':          str(msg.id),
                'msg_type':    'message',
                'content':     msg.content,
                'sender_id':   str(self.user.id),
                'sender_name': sender_name,
                'created_at':  msg.created_at.isoformat(),
            }
            await self.channel_layer.group_send(self.group_name, event)
            # Push real-time notification to the other party's personal channel
            await self._push_notification(sender_name, msg.content[:60], msg_type='new_message')

        elif msg_type == 'file':
            file_url  = data.get('file_url', '')
            file_name = data.get('file_name', '')
            file_size = data.get('file_size')
            mime_type = data.get('mime_type', 'application/octet-stream')
            if not file_url:
                return
            msg = await self._save_file_message(file_url, file_name, file_size, mime_type)
            sender_name = getattr(self.user, 'full_name', None) or self.user.email
            event = {
                'type':        'doctor_chat_message',
                'id':          str(msg.id),
                'msg_type':    'file',
                'content':     '',
                'file_url':    file_url,
                'file_name':   file_name,
                'file_size':   file_size,
                'mime_type':   mime_type,
                'sender_id':   str(self.user.id),
                'sender_name': sender_name,
                'created_at':  msg.created_at.isoformat(),
            }
            await self.channel_layer.group_send(self.group_name, event)
            preview = f'📎 {file_name}' if file_name else '📎 File'
            await self._push_notification(sender_name, preview, msg_type='new_message')

        elif msg_type == 'typing':
            await self.channel_layer.group_send(self.group_name, {
                'type':      'doctor_chat_typing',
                'sender_id': str(self.user.id),
                'is_typing': bool(data.get('is_typing', False)),
            })

    # ── Group event handlers ─────────────────────────────────────────────────

    async def doctor_chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type':        event.get('msg_type', 'message'),
            'id':          event['id'],
            'content':     event.get('content', ''),
            'file_url':    event.get('file_url'),
            'file_name':   event.get('file_name'),
            'file_size':   event.get('file_size'),
            'mime_type':   event.get('mime_type'),
            'metadata':    event.get('metadata'),
            'sender_id':   event['sender_id'],
            'sender_name': event['sender_name'],
            'created_at':  event['created_at'],
            'is_own':      event['sender_id'] == str(self.user.id),
        }))

    async def doctor_chat_typing(self, event):
        if event['sender_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type':      'typing',
                'sender_id': event['sender_id'],
                'is_typing': event['is_typing'],
            }))

    async def doctor_session_status(self, event):
        await self.send(text_data=json.dumps({
            'type':   'session_status',
            'status': event['status'],
        }))

    # ── DB helpers ───────────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_session(self):
        from apps.doctor_portal.models import ConsultationSession
        try:
            session = ConsultationSession.objects.select_related(
                'doctor__user', 'patient__user'
            ).get(id=self.session_id)
            # Only the doctor or the patient may join
            allowed = {str(session.doctor.user_id), str(session.patient.user_id)}
            if str(self.user.id) not in allowed:
                return None
            if session.status not in ('REQUESTED', 'ACTIVE', 'ACCEPTED', 'COMPLETED'):
                return None
            return session
        except ConsultationSession.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_history(self):
        from apps.doctor_portal.models import ConsultationMessage
        msgs = ConsultationMessage.objects.filter(
            session_id=self.session_id
        ).select_related('sender').order_by('created_at')[:100]
        return [
            {
                'type':        m.message_type or 'message',
                'id':          str(m.id),
                'content':     m.content,
                'file_url':    m.file_url,
                'file_name':   m.file_name,
                'file_size':   m.file_size,
                'mime_type':   m.mime_type,
                'metadata':    m.metadata,
                'sender_id':   str(m.sender_id),
                'sender_name': getattr(m.sender, 'full_name', None) or m.sender.email,
                'created_at':  m.created_at.isoformat(),
                'is_own':      str(m.sender_id) == str(self.user.id),
            }
            for m in msgs
        ]

    @database_sync_to_async
    def _save_message(self, content: str):
        from apps.doctor_portal.models import ConsultationMessage
        return ConsultationMessage.objects.create(
            session_id   = self.session_id,
            sender       = self.user,
            content      = content,
            message_type = 'text',
        )

    @database_sync_to_async
    def _save_file_message(self, file_url, file_name, file_size, mime_type):
        from apps.doctor_portal.models import ConsultationMessage
        return ConsultationMessage.objects.create(
            session_id   = self.session_id,
            sender       = self.user,
            content      = '',
            message_type = 'file',
            file_url     = file_url,
            file_name    = file_name,
            file_size    = file_size,
            mime_type    = mime_type,
        )

    @database_sync_to_async
    def _get_other_user_id(self):
        """Return the user_id of the other party in the session."""
        session = self.session
        doctor_uid  = str(session.doctor.user_id)
        patient_uid = str(session.patient.user_id)
        return patient_uid if str(self.user.id) == doctor_uid else doctor_uid

    async def _push_notification(self, sender_name: str, preview: str, msg_type: str = 'new_message'):
        """Send a real-time notification event to the other party's personal WS channel."""
        other_uid = await self._get_other_user_id()
        await self.channel_layer.group_send(
            f'user_notif_{other_uid}',
            {
                'type':    'user_notification',
                'payload': {
                    'type':       msg_type,
                    'from':       sender_name,
                    'preview':    preview,
                    'session_id': self.session_id,
                },
            }
        )
