# User pilot protocol

Status: prepared, not yet run. The evaluation so far uses labeled synthetic data and no real users. This short pilot adds human evidence for the business case. No result may be reported before the pilot has taken place.

**Goal.** Compare the time and success of finding the right person with LinkMate against a plain note search, and collect willingness to pay.

**Participants.** Five to eight students or freelancers who are not on the team. Record only a participant number. Participants use the synthetic dataset, never real contacts.

**Setup.** One laptop running LinkMate with the seeded data. A text file with all raw notes from `data/dataset/notes.jsonl`, opened in a text editor with its search function.

**Procedure, about 15 minutes per person.**

1. Explain the scenario: this is your network, these are your notes.
2. Assign six needs, three per tool, alternating which tool starts. Use the indirect questions t15, t17, t19, t24, t28 and t30.
3. For each need, measure the seconds until the participant names a person, and record whether the person is expected or acceptable (labels in `questions_test.jsonl`).
4. The participant captures one note about a person of their choice, fictional, and reviews the proposed profile. Record the seconds and the number of corrected fields.
5. Ask the questions below.

**Questions, 1 to 5 scale unless noted.**

| # | Question |
|---|---|
| 1 | The recommendation and its source helped me decide whom to contact |
| 2 | I trusted the answers |
| 3 | The weak match label was useful |
| 4 | I would capture notes this way after meeting someone |
| 5 | Would you pay for this? Nothing, up to $3, up to $6 or up to $12 per month |

**Record sheet.**

| Participant | Need | Tool | Seconds | Right person (y/n) |
|---|---|---|---|---|
| P1 | t15 | LinkMate | | |

**Report.** Median seconds and success per tool with the number of participants, the answers to the questions, and the limits: small sample, synthetic network, participants from the team's own surroundings.
