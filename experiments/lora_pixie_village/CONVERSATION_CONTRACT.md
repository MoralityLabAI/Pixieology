# Two-agent conversation contract

Phase 1 has exactly two ordered residents. The server, never either model,
selects the next speaker. One turn contains one public message. A session is
always a conversation first; no Storyworld is required to create or advance it.

## Isolation

An agent request contains its own private system prompt plus a public context
packet: room ID, topic, its public name, the other public name, turn number, and
the bounded public transcript. It must not contain the other agent's system
prompt, provider configuration, endpoint, API-key environment name, model
routing, or adapter path.

The browser receives a redacted public configuration. It cannot nominate an
endpoint or adapter in a step request; it submits only the session ID.

## State transition

The state transition is:

1. load the last atomic session snapshot;
2. derive the next speaker from `turn_index % 2`;
3. build the isolated bounded context;
4. invoke that speaker's server-side provider;
5. validate and normalize public speech;
6. fsync the turn event;
7. atomically replace the session snapshot.

A provider error is logged separately and cannot increment `turn_index` or
alter the public transcript. Because the API is step-based, pause means simply
not requesting another transition; no hidden generation loop continues.

## Optional Storyworld decision thread

A validated Storyworld may be projected into a server-whitelisted public
decision card and attached to an already-running conversation. Attachment keeps
the prior transcript, records the exact turn boundary, and defaults to
`deliberation_only`. The model-visible card contains only situation, location,
explicitly declared visible facts, public constraints, and legal options. Audit
metadata remains in the session but is stripped from the model request.

Each decision response ends with exactly one `[proposal:ACTION_ID]` marker. The
server rejects missing, duplicate, or illegal markers, strips the valid marker
from public speech, and stores `proposed_action_id` in the turn receipt.

Canonical execution is a separate experimental path, not the default thread
behavior. When explicitly enabled for a decision session, the bridge applies
one action per turn and never implements its own outcome logic. The engine is
reconstructed by reset plus receipt replay; hidden engine state is never placed
in the public session. Agent-private evidence and evaluator state remain outside
this layer.
