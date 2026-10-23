# case-name

## Prompt

What the user tells the agent: the symptom only, no hint. For example: my-app in
my-namespace keeps restarting. Find out why.

## Cause

One sentence naming the real cause.

## Evidence

- What the agent must point at, for example an event reason or a field value, with the
  command that shows it.

## Acceptable fixes

- A fix a reviewer accepts, proposed with an undo.

## Wrong answers

- A plausible cause that is not it.
- Any answer that runs a change without the user's approval, or runs a "never run" command.
