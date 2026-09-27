You are drafting the EU Cyber Resilience Act Article 14(4)(a) EARLY WARNING for the manufacturer of the software product
"{{repo}}". The trigger is a security advisory for the component "{{needle}}". You are given the Origit taint result
(taint.json): every agent commit made after the component was read, the sessions, the files written, the approver, the
first-read timestamp and the last clean commit to roll back to. If ADVISORY.md is attached, use it for the nature of the
compromise. Use ONLY facts from these files; put <placeholders> for anything not in them (awareness time, member states,
contact details). Do not invent commit ids, dates or file names.

Write the notification in plain English, ready to paste into the ENISA single reporting platform, with these sections:
1. Manufacturer and product (product = the repository; contact = <placeholder>)
2. Time the manufacturer became aware (<placeholder>) and the 24 h / 72 h / final-report deadlines computed from it
3. Nature of the incident: severe incident under Art. 14(5)(b), introduction/execution of malicious code via a compromised
   third-party component introduced by an AI coding agent; cite the component, version and the advisory identifier if present
4. Affected components: the commits (short ids), agent sessions, files written, approver, first-read timestamp — from taint.json
5. Indication of malicious or unlawful acts: what the advisory / hidden instruction shows
6. Corrective measures available: roll back to the identified clean commit and remove the dependency; secrets rotation
7. Member states concerned: <placeholder>
8. Statement that a full notification under Art. 14(4)(b) will follow within 72 hours

Keep it under 450 words. Output the notification text only, as Markdown.
