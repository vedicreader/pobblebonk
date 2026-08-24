"""A minimal ACP agent, so a test can drive `AcpRunner` over the real wire protocol.

`STUB_TOOL` makes it ask permission for a write before answering; `STUB_LOAD=fail` makes it refuse
an unknown session id, the way a real agent does rather than handing back the wrong conversation.
"""
import asyncio, os, sys

import acp
from acp.schema import (AgentCapabilities, Implementation, InitializeResponse, LoadSessionResponse,
                        NewSessionResponse, PermissionOption, PromptResponse, ToolCallUpdate)

OPTIONS = [PermissionOption(option_id='allow_once', name='Allow', kind='allow_once'),
           PermissionOption(option_id='reject_once', name='Reject', kind='reject_once')]


class Stub(acp.Agent):
    "Answers one prompt with a line naming its session and how many turns it has had."

    def __init__(self): self.turns, self.conn = {}, None

    def on_connect(self, conn): self.conn = conn

    async def initialize(self, protocol_version, client_capabilities=None, client_info=None, **kw):
        return InitializeResponse(
            protocol_version=min(protocol_version, acp.PROTOCOL_VERSION),
            agent_capabilities=AgentCapabilities(load_session=True),
            agent_info=Implementation(name='stub', title='Stub', version='0'))

    async def new_session(self, cwd, **kw):
        sid = f'stub-{len(self.turns)+1}'
        self.turns[sid] = 0
        return NewSessionResponse(session_id=sid)

    async def load_session(self, cwd, session_id, **kw):
        if session_id not in self.turns:
            if os.environ.get('STUB_LOAD') == 'fail':
                raise acp.RequestError.resource_not_found(session_id)
            self.turns[session_id] = 0
        return LoadSessionResponse()

    async def prompt(self, session_id, prompt, **kw):
        text = ' '.join(getattr(b, 'text', '') or '' for b in prompt)
        self.turns[session_id] = self.turns.get(session_id, 0) + 1
        if os.environ.get('STUB_TOOL'):
            tc = ToolCallUpdate(tool_call_id='t1', title='create_file', kind='edit')
            r = await self.conn.request_permission(session_id=session_id, tool_call=tc, options=OPTIONS)
            oid = getattr(r.outcome, 'option_id', '') or ''
            await self.conn.session_update(session_id, acp.update_agent_message_text(
                f"the write was {'allowed' if oid.startswith('allow') else 'refused'}. "))
        await self.conn.session_update(session_id, acp.update_agent_message_text(
            f'turn {self.turns[session_id]} of {session_id} read: {text}'))
        return PromptResponse(stop_reason='end_turn')

    async def cancel(self, session_id, **kw): pass


async def serve():
    reader, writer = await acp.stdio_streams()
    sys.stdout = sys.stderr    # stdout is the protocol; anything that prints must not corrupt a frame
    await acp.run_agent(Stub(), input_stream=writer, output_stream=reader)


if __name__ == '__main__': asyncio.run(serve())
