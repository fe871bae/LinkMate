"""Extend the synthetic dataset to 55 contacts and write the held-out test questions.

Usage: python data/dataset/source/build_extension.py

The script is idempotent. IDs are derived from fixed strings, so a rerun gives the
same files. The held-out questions were written before the answer gate was tuned
and are only used for the final evaluation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from linkmate.models import Contact, Fact, Note

ROOT = Path(__file__).resolve().parents[1]

LONG_EMAIL = (
    "Hi! Great meeting you at the embedded systems night. As promised, a bit about what I do. "
    "I'm Jonas Keller, firmware engineer at Brightcell Energy in Long Beach. Most of my week goes into "
    "battery management systems for small electric vehicles, which means a lot of time with safety reviews, "
    "supplier calls and test reports, so honestly the job is less glamorous than it sounds. We moved offices "
    "in spring, the new place is right next to the harbor and the coffee is finally decent. Outside of work "
    "I'm restoring an old Vespa with my brother, which is going slowly because neither of us owns the right "
    "tools. If you ever come by the harbor let me know, there is a good taco truck on Thursdays. "
    "Back to your project: you said your board keeps crashing. I've spent years on bare-metal C and FreeRTOS "
    "on STM32 chips, so I'm happy to debug your firmware with you over a video call, just send me the code "
    "and a description of when the resets happen. Best, Jonas"
)

# name, aliases, organization, role, location, met_context, summary, notes, facts
# notes: (text, source_type, created_at). facts: (kind, value, note index).
CONTACTS = [
    ("Hugo Lindgren", [], "", "Carpenter", "Long Beach, CA", "Neighbor",
     "Neighbor and carpenter who builds furniture.",
     [("Hugo next door builds furniture for a living. Said he'd fix my shelf.", "note", "2026-09-02T18:00:00Z")],
     [("skill", "furniture building", 0), ("offers_help", "fix a shelf", 0)]),
    ("Priscilla Owens", [], "Harbor Realty", "Real estate agent and notary public", "Long Beach, CA", "Lease signing",
     "Real estate agent who also works as a notary.",
     [("Priscilla Owens, Harbor Realty. Realtor, also a notary public. Notarized my lease papers for free, said to call again if I need something notarized.", "note", "2026-03-11T16:00:00Z")],
     [("skill", "real estate sales", 0), ("skill", "notary public", 0), ("offers_help", "notarize documents", 0)]),
    ("Dmitri Volkov", ["Dima"], "Long Beach Chess Club", "Chess coach", "Long Beach, CA", "Chess club",
     "Chess coach who also knows competitive programming.",
     [("dima (dmitri volkov) -> chess club thurs nights. coach, 2300 rating. would coach me for free if i bring coffee", "note", "2026-01-22T03:00:00Z"),
      ("Dmitri also did competitive programming in college, ICPC regionals. Knows graph algorithms really well.", "note", "2026-05-14T04:00:00Z")],
     [("skill", "chess coaching", 0), ("offers_help", "chess coaching", 0), ("skill", "competitive programming", 1), ("skill", "graph algorithms", 1)]),
    ("Fatima Rahman", [], "Bayview Clinic", "Registered dietitian", "Long Beach, CA", "Health fair on campus",
     "Dietitian who offered to review a meal plan.",
     [("Fatima Rahman, registered dietitian at Bayview Clinic, had a booth at the campus health fair. Works a lot with student athletes and people with low energy or iron deficiency. Offered to look at my meal plan if I log a week of food.", "note", "2026-04-08T19:00:00Z")],
     [("skill", "nutrition counseling", 0), ("skill", "sports nutrition", 0), ("offers_help", "review a meal plan", 0)]),
    ("Gabriel Santos", ["Gabo"], "CSULB Language Center", "Spanish instructor", "Long Beach, CA", "Language exchange",
     "Spanish instructor who runs conversation practice.",
     [("Gabo, teaches Spanish at the CSULB language center. Runs a conversation table every Wednesday and said I should just show up to practice speaking.", "note", "2026-02-18T20:00:00Z")],
     [("skill", "Spanish teaching", 0), ("offers_help", "Spanish conversation practice", 0)]),
    ("Hana Kovac", [], "Granite Climbing Gym", "Route setter", "Signal Hill, CA", "Climbing gym",
     "Route setter who can teach belaying.",
     [("Hana Kovac sets routes at Granite Climbing Gym. Told me she can show me how to belay properly and check me off for the top rope wall.", "note", "2026-06-03T02:00:00Z")],
     [("skill", "indoor climbing", 0), ("offers_help", "teach belaying", 0)]),
    ("Isaac Goldberg", [], "", "Freelance bookkeeper", "Long Beach, CA", "Freelancer coworking space",
     "Bookkeeper for freelancers. Does not file taxes.",
     [("Isaac Goldberg does bookkeeping for freelancers at the coworking space, mostly QuickBooks setup and invoices. He was clear that he does not file tax returns, but he'd set up my books.", "note", "2026-07-01T17:00:00Z")],
     [("skill", "bookkeeping", 0), ("skill", "QuickBooks", 0), ("offers_help", "set up QuickBooks books", 0)]),
    ("Jonas Keller", [], "Brightcell Energy", "Firmware engineer", "Long Beach, CA", "Embedded systems night",
     "Firmware engineer who offered to debug STM32 firmware.",
     [(LONG_EMAIL, "email", "2026-08-19T15:00:00Z")],
     [("skill", "battery management systems", 0), ("skill", "bare-metal C and FreeRTOS", 0), ("skill", "STM32", 0), ("offers_help", "debug firmware", 0)]),
    ("Kira Novak", [], "", "Freelance video editor", "Los Angeles, CA", "Student film screening",
     "Video editor who offered to cut a short pitch video.",
     [("Kira Novak, freelance video editor, cuts YouTube explainers and short films. Met at a student film screening. Offered to cut our pitch video if we send the raw footage a week ahead. Color grading is her favorite part.", "note", "2026-10-02T04:00:00Z")],
     [("skill", "video editing", 0), ("skill", "color grading", 0), ("offers_help", "cut a pitch video", 0)]),
    ("Liam Walsh", [], "", "", "", "Coffee place",
     "Barely known contact who might know about boats.",
     [("Liam, guy from the coffee place. Something with boats?", "note", "2026-09-20T16:00:00Z")],
     [("interest", "boats", 0)]),
    ("Amara Okoye", [], "Harbor Community Fund", "Grant writer", "Long Beach, CA", "Volunteer day",
     "Grant writer who offered to read a grant application.",
     [("Amara Okoye writes grants for the Harbor Community Fund. Met at the volunteer day. She has won a lot of funding for nonprofits and said she'd read a draft of a grant application if we ever write one.", "note", "2026-05-27T18:00:00Z")],
     [("skill", "grant writing", 0), ("skill", "nonprofit fundraising", 0), ("offers_help", "read a grant application draft", 0)]),
    ("Ruth Feldman", [], "Red Cross Long Beach", "Retired nurse, volunteer instructor", "Long Beach, CA", "Neighborhood meeting",
     "Retired nurse who teaches first aid and CPR.",
     [("Ruth Feldman, retired ER nurse. Teaches CPR and first aid classes for the Red Cross on weekends. Said she'd save me a spot in the next class.", "note", "2026-03-30T22:00:00Z")],
     [("skill", "emergency nursing", 0), ("skill", "CPR and first aid instruction", 0), ("offers_help", "spot in a CPR class", 0)]),
    ("Theo Laurent", [], "", "Freelance translator", "Long Beach, CA", "French film night",
     "Translator who offered to translate documents into French.",
     [("Theo Laurent, native French speaker, works as a freelance translator (English to French, mostly technical manuals). Said he can translate short documents for me.", "note", "2026-02-02T05:00:00Z")],
     [("skill", "English to French translation", 0), ("offers_help", "translate short documents", 0)]),
    ("Sanjay Mehta", [], "CSULB High Performance Computing", "Cluster administrator", "Long Beach, CA", "ML reading group",
     "Cluster admin who can give students GPU access.",
     [("Sanjay Mehta runs the CSULB HPC cluster. Mentioned at the reading group that students can request GPU time through him, and he can help move big training jobs off a laptop.", "note", "2026-09-11T23:00:00Z")],
     [("skill", "HPC cluster administration", 0), ("offers_help", "request GPU time", 0), ("offers_help", "move training jobs to the cluster", 0)]),
    ("Wendy Zhao", [], "Long Beach Legal Aid", "Housing mediator", "Long Beach, CA", "Tenant workshop",
     "Housing mediator who advises tenants on disputes.",
     [("Wendy Zhao, housing mediator at Long Beach Legal Aid. Ran the tenant workshop. Handles disputes between renters and landlords, including security deposits. Told us to call her office for free advice.", "note", "2026-08-05T20:00:00Z")],
     [("skill", "tenant rights", 0), ("skill", "housing mediation", 0), ("offers_help", "free tenant advice", 0)]),
]

# id, type, difficulty, question, expected names, acceptable names, rationale
QUESTIONS = [
    ("t01", "direct", "easy", "Who could build a piece of furniture or fix a shelf for me?", ["Hugo Lindgren"], [], "Hugo builds furniture."),
    ("t02", "direct", "easy", "I need a document notarized. Who can do that?", ["Priscilla Owens"], [], "Priscilla is a notary."),
    ("t03", "direct", "easy", "Who could coach me to get better at chess?", ["Dmitri Volkov"], [], "Dmitri coaches chess."),
    ("t04", "direct", "easy", "Who can review my meal plan?", ["Fatima Rahman"], [], "Fatima is a dietitian and offered this."),
    ("t05", "direct", "easy", "Who can I practice Spanish conversation with?", ["Gabriel Santos"], [], "Gabriel runs a conversation table."),
    ("t06", "direct", "easy", "Who can teach me how to belay at a climbing gym?", ["Hana Kovac"], [], "Hana offered this."),
    ("t07", "direct", "easy", "Who can set up QuickBooks for my freelance invoices?", ["Isaac Goldberg"], [], "Isaac does this."),
    ("t08", "direct", "medium", "Who could help me debug firmware on an STM32 board?", ["Jonas Keller"], ["Patrick Sullivan"], "The offer sits at the end of a long email."),
    ("t09", "direct", "easy", "Who can edit a short pitch video for us?", ["Kira Novak"], [], "Kira offered this."),
    ("t10", "direct", "easy", "Who has experience writing grant applications?", ["Amara Okoye"], [], "Amara writes grants."),
    ("t11", "direct", "easy", "Where can I take a CPR and first aid class?", ["Ruth Feldman"], [], "Ruth teaches these classes."),
    ("t12", "direct", "easy", "Who can translate a short document into French?", ["Theo Laurent"], [], "Theo is a translator."),
    ("t13", "direct", "easy", "Who can get me GPU time on a cluster?", ["Sanjay Mehta"], [], "Sanjay runs the cluster."),
    ("t14", "direct", "easy", "Who can advise me about my rights as a tenant?", ["Wendy Zhao"], ["Olivia Park"], "Wendy handles this."),
    ("t15", "indirect", "medium", "My landlord is keeping my deposit and doesn't answer my messages.", ["Wendy Zhao"], ["Olivia Park"], "Security deposit disputes."),
    ("t16", "indirect", "medium", "We filmed our two minute demo and the raw footage looks terrible.", ["Kira Novak"], [], "Video editing."),
    ("t17", "indirect", "medium", "My microcontroller keeps resetting a few seconds after I flash it.", ["Jonas Keller"], ["Patrick Sullivan"], "Firmware debugging, in the tail of a long email."),
    ("t18", "indirect", "medium", "Training my model keeps crashing my laptop because it runs out of memory.", ["Sanjay Mehta"], ["Marcus Bell"], "Moving jobs off a laptop."),
    ("t19", "indirect", "medium", "I've been tired all the time and I suspect it has to do with what I eat.", ["Fatima Rahman"], ["Hannah Vogel"], "Nutrition and low energy."),
    ("t20", "indirect", "medium", "My grandmother collapsed last year and I had no idea what to do. I never want to feel that helpless again.", ["Ruth Feldman"], ["Hannah Vogel"], "First aid training."),
    ("t21", "indirect", "medium", "I want to understand how investors will look at our startup before we talk to them.", ["Daniel Kim"], ["Omar Siddiqui", "Ben Adeyemi"], "Fundraising and pitch decks."),
    ("t22", "indirect", "medium", "My hips feel stiff from sitting at my desk all day.", ["Aisha Bello"], ["Victor Nguyen"], "Yoga and mobility coaching."),
    ("t23", "indirect", "medium", "People get lost on our app's checkout screen and we don't know why.", ["Julia Brenner"], ["Ben Adeyemi"], "Usability testing and UX."),
    ("t24", "indirect", "medium", "My application letter for a job in Berlin needs a native speaker's eye.", ["Anna Schmidt"], ["Sarah Whitfield", "Julia Brenner"], "German proofreading."),
    ("t25", "indirect", "medium", "I want to understand how many hours my student visa lets me work off campus.", ["Sofia Alvarez"], [], "F-1 regulations."),
    ("t26", "indirect", "medium", "I'd like to spend a weekend sleeping outdoors in the mountains but I own no equipment.", ["Chris Douglas"], [], "Camping gear and trails."),
    ("t27", "indirect", "medium", "A bigger company is using our logo. Are we protected?", ["Olivia Park"], [], "Intellectual property."),
    ("t28", "indirect", "easy", "My lease ends soon and I need a new place to live near campus.", ["Maria Gonzalez"], ["Priscilla Owens"], "Apartment leasing."),
    ("t29", "indirect", "hard", "The bank wants to see what our company could be worth in five years.", ["Omar Siddiqui"], ["Daniel Kim", "Noah Becker"], "DCF valuation."),
    ("t30", "indirect", "easy", "I found a cheap used car but I don't trust the seller.", ["Felipe Costa"], [], "Used car inspection."),
    ("t31", "none", "hard", "Who can teach me Italian?", [], [], "Near misses: Gabriel teaches Spanish, Theo translates French."),
    ("t32", "none", "hard", "Who can repair my washing machine?", [], [], "Near misses: Felipe repairs cars, Hugo builds furniture."),
    ("t33", "none", "hard", "Who could guide a mountaineering expedition in the Himalayas?", [], [], "Near misses: Chris organizes Sierra hikes, Hana sets gym routes."),
    ("t34", "none", "easy", "Do I know a dentist who could look at my tooth?", [], [], "Nobody works in dentistry."),
    ("t35", "none", "hard", "Who knows how to file a patent in Japan?", [], [], "Near miss: Olivia does IP law, but not Japanese filings."),
    ("t36", "none", "medium", "Who can coach my swimming for a triathlon?", [], [], "Near misses: Victor treats runners, Aisha teaches yoga."),
    ("t37", "none", "hard", "Who can tune and repair my cello?", [], [], "Near miss: Luca plays guitar."),
    ("t38", "none", "hard", "Who has hands-on experience with quantum computing hardware?", [], [], "Near misses: Patrick does electronics, Sanjay runs a GPU cluster."),
    ("t39", "none", "hard", "Who can help me buy a vacation house in Spain?", [], [], "Near misses: Priscilla sells real estate in Long Beach, Gabriel teaches Spanish."),
    ("t40", "none", "easy", "Who could babysit my kids this Saturday?", [], [], "Nobody offers childcare."),
]


def stable_id(prefix: str, text: str) -> str:
    return f"{prefix}{hashlib.sha1(text.encode()).hexdigest()[:8]}"


def build_contact(row: tuple) -> Contact:
    name, aliases, organization, role, location, met, summary, notes, facts = row
    note_models = [
        Note(id=stable_id("n_", f"{name}:{number}"), text=text, source_type=source, created_at=datetime.fromisoformat(created))
        for number, (text, source, created) in enumerate(notes)
    ]
    merged: list[Fact] = []
    for kind, value, index in facts:
        merged.append(Fact(kind=kind, value=value, source_note_ids=[note_models[index].id]))
    return Contact(
        id=stable_id("c_", name), name=name, aliases=aliases, organization=organization, role=role,
        location=location, met_context=met, summary=summary, notes=note_models, facts=merged,
        created_at=note_models[0].created_at, updated_at=note_models[-1].created_at,
    )


def main() -> None:
    new_contacts = [build_contact(row) for row in CONTACTS]
    for contact in new_contacts:
        (ROOT / "contacts" / f"{contact.id}.json").write_text(contact.model_dump_json(indent=2) + "\n", encoding="utf-8")

    all_contacts = [Contact.model_validate_json(path.read_text("utf-8")) for path in sorted((ROOT / "contacts").glob("c_*.json"))]
    ids = {contact.name: contact.id for contact in all_contacts}

    path = ROOT / "notes.jsonl"
    rows = {row["note_id"]: row for row in map(json.loads, path.read_text("utf-8").splitlines())}
    for contact in new_contacts:
        for note in contact.notes:
            rows[note.id] = {
                "note_id": note.id, "contact_id": contact.id, "contact_name": contact.name,
                "source_type": note.source_type, "created_at": note.created_at.isoformat().replace("+00:00", "Z"),
                "text": note.text,
            }
    ordered = sorted(rows.values(), key=lambda row: row["created_at"])
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ordered), encoding="utf-8")

    with (ROOT / "questions_test.jsonl").open("w", encoding="utf-8") as out:
        for qid, qtype, difficulty, question, expected, acceptable, rationale in QUESTIONS:
            out.write(json.dumps({
                "id": qid, "type": qtype, "difficulty": difficulty, "question": question,
                "expected_contact_ids": [ids[name] for name in expected], "expected_contact_names": expected,
                "acceptable_contact_ids": [ids[name] for name in acceptable], "acceptable_contact_names": acceptable,
                "rationale": rationale,
            }, ensure_ascii=False) + "\n")
    print(f"{len(all_contacts)} contacts, {len(ordered)} notes, {len(QUESTIONS)} held-out questions.")


if __name__ == "__main__":
    main()
