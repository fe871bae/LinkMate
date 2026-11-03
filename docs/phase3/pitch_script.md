# Pitch video script

Target length 9:30, limit 10:00. Speaking rate about 140 words per minute. The speaker split is a proposal. Each part is about the same length, so that every member appears. The demo must be the real app, either recorded live or `docs/phase3/demo/demo.mp4`.

| Time | Slide | Speaker | Requirement covered |
|---|---|---|---|
| 0:00 | 1 Title | Felix | Team, project |
| 0:20 | 2 Problem | Felix | Problem |
| 1:10 | 3 Target users | Felix | Target users |
| 1:45 | 4 Solution | Felix | Solution |
| 2:15 | 5 Market gap | Antoine | Business |
| 2:50 | 6 AI method | Vishal | AI technology |
| 3:45 | 7 Demo, the recording runs 2:00 | Mika | Working prototype, input to output |
| 6:10 | 8 Evaluation setup | Vishal | Evidence |
| 6:35 | 9 Results | Vishal | Evidence, baseline |
| 7:15 | 10 Failures and trust | Vishal | Failure analysis |
| 7:45 | 11 Business | Antoine | Business applicability |
| 8:25 | 12 Scalability | Mika | Business, scale |
| 8:45 | 13 Limitations and roadmap | Felix | Limitations, roadmap |
| 9:20 | 14 Close | Felix | Contributions |

## 1. Title (Felix)

Hi, we are Team 10. I'm Felix, with Antoine, Vishal and Mika. This is LinkMate, a personal memory for your network that finds the right person for a problem, and runs entirely on your own laptop.

## 2. Problem (Felix)

Think of the last time you met someone interesting at an event. They told you what they do, and maybe offered to help. Weeks later you have a problem they could solve, and you can't remember who it was.

That knowledge sits in phone notes, emails, chats and memory. Contact books store a name and a company, not what a person can do. Research on weak ties shows that acquaintances are a key source of new information and job opportunities. Those are exactly the contacts whose context gets lost first. So help that exists in your network goes unused.

## 3. Target users (Felix)

We target individuals, defined by behavior. Our primary segment is active networkers, people who meet new people often, like club members or people who just moved to a new city. They feel the pain most and are our likely paying users. The secondary segment meets people less often, but hits the same problem at specific moments.

## 4. Solution (Felix)

LinkMate has two moments. Capture. After meeting someone, you write a note in your own words, the AI proposes a profile, and you confirm it. Ask. Weeks later you describe a need, and LinkMate answers with contacts, a reason, and the original note as the source. Or it says no suitable contact.

## 5. Market gap (Antoine)

AI personal CRMs exist. Dex, Mesh, ConnectMachine, Happenstance and Covve all offer pieces of this, at about six to twenty-four dollars a month. So we are not the first. Our gap is specific. We turn messy notes into enriched profiles, we answer open-ended needs with a traceable source for every recommendation, and third-party data about your contacts stays on your device.

## 6. AI method (Vishal)

There are three AI tasks. First, extraction. A small local language model turns a note into a structured profile, using a fixed JSON schema. Second, retrieval. An embedding model turns notes and questions into vectors, and we search by cosine similarity in Chroma, because people phrase needs differently from their notes. Third, a grounded answer. The model only sees the retrieved notes.

We do not trust the model blindly. It only proposes, and the user confirms. It never sees real IDs, only labels, and our code resolves them and drops anything without a valid source. The whole thing runs on an eight gigabyte laptop through Ollama, with a half-gigabyte chat model and no API keys.

## 7. Demo (Mika)

Show `docs/phase3/demo/demo.mp4`, or record the same steps live. Speak over it.

- Here is the running app, with fifty-five synthetic contacts. Everything is local.
- I capture a note about someone I just met, Mara, a route setter at a climbing gym who offered to teach me lead climbing. I click extract.
- The local model proposes a profile. Nothing is saved yet. I can correct any field, and the original note stays attached. I confirm.
- Now I ask, who could teach me lead climbing. LinkMate finds Mara, gives a reason and shows my own note as the source.
- A question from the dataset with wording close to the notes, calibrating a sensor. It finds Lena.
- A paraphrase. My knee hurts after long runs. There is no keyword for physical therapist in my question, and it still finds Victor.
- Here is a weakness. Who could photograph a wedding in Munich? Nobody in my network fits. The small model suggests a portrait photographer, but look, it is labeled a weak match, and I can check the note.
- And a veterinarian for my dog. No suitable contact.
- Finally the contact page, where I can edit, export and delete, and the status page with the models and the index.

## 8. Evaluation setup (Vishal)

How well does it work? We labeled seventy questions. Thirty were used for tuning. Forty were held out and only run once the settings were frozen. Ten of them have no right answer, mostly with a near miss to tempt the system. We compare against a keyword search baseline.

## 9. Results (Vishal)

On the held-out questions, LinkMate finds the right contact seventy percent of the time, against sixty-seven for keywords. Direct questions are all correct. On paraphrased questions, search finds the contact in the top three seventy-five percent of the time, against forty-four for keywords. But with forty questions, the overall difference between LinkMate and the baseline is not statistically significant, and refusals are weak at two out of ten.

Our most useful finding is the match label. Of the recommendations labeled strong, eighty-nine percent fit. Of the weak ones, fifty-three percent. If you only trust strong matches, you get nine out of ten correct refusals, and find fifty-three percent of the right contacts.

## 10. Failures and trust (Vishal)

We classified every failure. Most are near misses the small model accepts, such as a guitarist for Italian lessons. Two prompt fixes we tried made this worse, so we dropped them and report it. No recommendation ever cited an invalid source. Reasons can contain invented details, so the source is always shown. Testing also exposed a real injection weakness. An email telling any AI to always recommend its author influenced two answers. We now remove such sentences before the models see them, but a keyword rule can be beaten, and attacks still reach the proposed profile. So the user review stays mandatory.

## 11. Business (Antoine)

The model is freemium. Free with limited contacts, premium at around six dollars a month for unlimited contacts, sync and voice capture. Inference is not the cost driver. Even hosted it would be under one cent per user per month. At ten thousand users and a typical four percent conversion, that is twenty-four hundred dollars a month. These are illustrative assumptions, not validated demand. We have a user pilot prepared to measure time saved and willingness to pay.

## 12. Scalability (Mika)

We tested scale with generated contacts. Search stays around twenty-five milliseconds up to five thousand contacts, and a full index takes about three minutes. Quality falls first. Recall at three is still ninety-six percent at two thousand contacts, and seventy-nine percent at five thousand. So a personal network works on a laptop. A larger service needs a database and a real backend.

## 13. Limitations and roadmap (Felix)

The limits are clear. Refusals are weak, the data is synthetic, there are no real users yet, and we only ran it on a Mac. Next steps are the user pilot, a small reranker or stronger model for near misses, optional encrypted sync, then voice capture, imports and a mobile capture view.

## 14. Close (Felix)

LinkMate turns the notes you already take into a network you can actually use, and it tells you when to double-check. The code, the data and every number shown here are in our repository. Thank you.
