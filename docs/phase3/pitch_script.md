# Pitch video script

Estimated length 9:43, limit 10:00. Speaking rate about 140 words per minute. The speaker split is a proposal: Felix 2:04, Antoine 1:48, Vishal 2:53, Mika 2:58. The demo must be the real app, either recorded live or `docs/phase3/demo/demo.mp4`. The same text is in the speaker notes of `LinkMate_Pitch_Slides.pptx`, and every number comes from `reports/evaluation/` or the final report.

| Time | Slide | Speaker | Requirement covered |
|---|---|---|---|
| 0:00 | 1 Title | Felix | Team, project |
| 0:17 | 2 Problem | Felix | Problem |
| 0:58 | 3 Target users | Felix | Target users |
| 1:22 | 4 Solution | Felix | Solution |
| 1:47 | 5 Market gap | Antoine | Business |
| 2:14 | 6 AI method | Vishal | AI technology |
| 2:54 | 7 Pipeline and guardrails | Vishal | AI technology, own contribution |
| 3:25 | 8 Architecture | Mika | Technical implementation |
| 3:53 | 9 Demo, the recording runs 2:00 | Mika | Working prototype, input to output |
| 5:58 | 10 Evaluation setup | Mika | Evidence |
| 6:23 | 11 Results | Vishal | Evidence, baseline |
| 6:49 | 12 Semantic search | Vishal | Evidence, analysis |
| 7:11 | 13 Match label | Vishal | Evidence, analysis |
| 7:32 | 14 Failures and trust | Vishal | Failure analysis |
| 8:05 | 15 Business | Antoine | Business applicability |
| 8:37 | 16 Scalability | Antoine | Business, scale |
| 9:02 | 17 Limitations and roadmap | Antoine | Limitations, roadmap |
| 9:26 | 18 Close | Felix | Contributions |

## 1. Title (Felix)

Hi, we are Team 10. I'm Felix, with Antoine, Vishal and Mika. This is LinkMate, a personal memory for your network. It finds the right person for a problem, and it runs entirely on your own laptop.

## 2. Problem (Felix)

Think of the last time you met someone interesting at an event. They told you what they do, and maybe offered to help. Weeks later you have a problem they could solve, and you can't remember who it was.

That knowledge sits in phone notes, emails and chats. Contact books store a name and a company, not what a person can do. Research shows that weak ties are a key source of new information and job opportunities, and their context gets lost first. So help that exists in your network goes unused.

## 3. Target users (Felix)

We target individuals, defined by behavior. Our primary segment is active networkers, like club members or people who just moved to a new city. They feel the pain most and are our likely paying users. Occasional networkers hit the same problem at specific moments, and we reach them through a free tier.

## 4. Solution (Felix)

LinkMate has two moments. Capture. After meeting someone, you write a note in your own words, the AI proposes a profile, and you confirm it. Ask. Weeks later you describe a need, and LinkMate answers with up to three contacts, a reason, and your original note as the source. Or it says no suitable contact.

## 5. Market gap (Antoine)

AI personal CRMs exist. Dex, Mesh, ConnectMachine, Happenstance and Covve offer pieces of this, at about six to twenty-four dollars a month. So we are not the first. Our gap is specific. We turn messy notes into enriched profiles, we answer open-ended needs with a traceable source for every recommendation, and third-party data about your contacts stays on your device.

## 6. AI method (Vishal)

There are three AI tasks. First, extraction. A small local language model turns a note into a structured profile, using a fixed JSON schema. Second, retrieval. An embedding model turns notes and questions into vectors, and we search by cosine similarity in Chroma, because people phrase needs differently from their notes. Third, a grounded answer. The model only sees the retrieved notes.

All of this runs through Ollama on an eight gigabyte laptop, with a half-gigabyte chat model and no API keys. A larger model did worse in the same pipeline.

## 7. Pipeline and guardrails (Vishal)

We do not trust the model blindly. Teal is AI, white is plain code, and coral is you. Nothing is saved until you confirm. When you ask, a similarity threshold comes first, so clearly unrelated questions never reach the chat model. The model sees neutral labels instead of real IDs, and our code drops anything without a valid source. The search score then sets a strong or weak label.

## 8. Architecture (Mika)

Technically, this is four layers on one machine. Streamlit pages only call services. Services use a core of pure functions and three infrastructure classes for Ollama, the contact store and the search index. JSON files are the source of truth, and the Chroma index can be rebuilt at any time. With a fake model plugged in, one hundred unit tests run without Ollama.

## 9. Demo (Mika)

Show docs/phase3/demo/demo.mp4 full screen, or record the same steps live. Speak over it. The slide is the storyboard and can stay visible as a lead-in.

- Here is the running app, with fifty-five synthetic contacts. Everything is local.
- I capture a note about someone I just met, Mara, a route setter at a climbing gym who offered to teach me lead climbing. I click extract.
- The local model proposes a profile. Nothing is saved yet. I can correct any field, and the original note stays attached. I confirm.
- Now I ask, who could teach me lead climbing. LinkMate finds Mara, gives a reason and shows my own note as the source.
- A question from the dataset with wording close to the notes, calibrating a sensor. It finds Lena.
- A paraphrase. My knee hurts after long runs. There is no keyword for physical therapist in my question, and it still finds Victor.
- Here is a weakness. Who could photograph a wedding in Munich? Nobody in my network fits. The small model suggests a portrait photographer, but look, it is labeled a weak match, and I can check the note.
- And a veterinarian for my dog. No suitable contact.
- Finally the contact page, where I can edit, export and delete, and the status page with the models and the index.

## 10. Evaluation setup (Mika)

How well does it work? We labeled seventy questions. Thirty were used for tuning. Forty were held out and only run once the settings were frozen. Ten of them have no right answer, mostly with a near miss to tempt the system. We compare against a keyword search baseline and a plain dense top hit.

## 11. Results (Vishal)

On the held-out questions, LinkMate finds the right contact seventy percent of the time, against sixty-seven for keywords. With forty questions that difference is not statistically significant. The language model does not add hits over the plain dense top hit. It adds the explanation and a small gain in refusals, which stay weak at two out of ten.

## 12. Semantic search (Vishal)

Where does semantic search help? Direct questions are all correct. On paraphrased questions, search finds the contact in the top three seventy-five percent of the time, against forty-four for keywords. A question takes one point two seconds at the median, and extraction gets all seventy names right.

## 13. Match label (Vishal)

Our most useful finding is the match label. Of the recommendations labeled strong, eighty-nine percent fit. Of the weak ones, fifty-three percent. If you only trust strong matches, you get nine out of ten correct refusals, and you still find sixteen of the thirty right contacts.

## 14. Failures and trust (Vishal)

We classified every failure. Most are near misses the small model accepts, such as a guitarist for Italian lessons. Two prompt fixes made this worse, so we dropped them. No recommendation ever cited an invalid source, but reasons can contain invented details, so the source is always shown. Testing also exposed a real injection weakness. We now remove such sentences, but a keyword rule can be beaten, so the user review stays mandatory.

## 15. Business (Antoine)

The model is freemium: free with limited contacts, premium at around six dollars a month. Inference is not the cost driver. Even hosted it would be under one cent per user per month. At ten thousand users and a typical four percent conversion, that is twenty-four hundred dollars a month. These are illustrative assumptions, not validated demand. We have a user pilot prepared to measure time saved and willingness to pay.

## 16. Scalability (Antoine)

We also tested scale with generated contacts. Search stays around twenty-five milliseconds up to five thousand contacts. Quality falls first. Recall at three is still ninety-six percent at two thousand contacts, and seventy-nine percent at five thousand. So a personal network works on a laptop. A larger service needs a database and a real backend.

## 17. Limitations and roadmap (Antoine)

The limits are clear. Refusals are weak, the data is synthetic, there are no real users yet, and we only ran it on a Mac. Next steps are the user pilot, a small reranker or stronger model for near misses, optional encrypted sync, then voice capture, imports and a mobile capture view.

## 18. Close (Felix)

LinkMate turns the notes you already take into a network you can actually use, and it tells you when to double-check. The code, the data and every number shown here are in our repository. Thank you.
