#!/usr/bin/env python3
"""Tag every chapter Q&A with IT-style types and add missing Short / Long /
Application / Competency questions so every subject matches the same bank tone.

    python3 scripts/enrich_qa.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CH_DIR = ROOT / "site" / "content" / "chapters"

INDIC_SLUGS = {"hindi", "sanskrit"}


def strip_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^[-*\d.)]+\s*", "", text.strip())
    return text.strip()


def first_str(items, default=""):
    for item in items or []:
        if isinstance(item, str) and item.strip():
            return strip_md(item)
    return default


def marks_n(q) -> int:
    try:
        return int(re.match(r"\d+", str(q.get("m", "3"))).group(0))
    except Exception:
        return 3


def infer_type(q) -> str:
    t = str(q.get("t") or "").upper()[:1]
    if t in {"S", "L", "A", "C"}:
        return t
    text = str(q.get("q", "")).lower()
    if any(
        k in text
        for k in (
            "read the following",
            "read and answer",
            "case-stud",
            "competency",
            "पढ़कर उत्तर",
            "निम्नलिखित",
        )
    ):
        return "C"
    if any(
        k in text
        for k in (
            "apply",
            "situation",
            "a student",
            "rewrite",
            "identify the violated",
            "suggest two",
            "in the laboratory",
            "in real life",
            "स्थिति",
            "प्रयोग",
        )
    ):
        return "A"
    n = marks_n(q)
    return "S" if n <= 3 else "L"


def indic(slug: str) -> bool:
    return slug in INDIC_SLUGS


def extras_for(ch: dict, slug: str) -> list[dict]:
    title = ch.get("title", "this chapter")
    short = strip_md(ch.get("short") or "")
    idea = first_str(ch.get("concepts"), short or title)
    idea_short = idea[:420].rstrip(" .") + "."
    mistake = first_str(ch.get("mistakes"), "Leaving out the key term or skipping a marked step.")
    trick = first_str(ch.get("tricks"), "Write the definition, then one example.")
    lens = first_str(ch.get("lens"), short)
    existing = ch.get("qa") or []
    sample_q = existing[0]["q"] if existing else f"State the central idea of {title}."
    sample_a = existing[0]["a"] if existing else idea_short
    if isinstance(sample_a, list):
        sample_a_txt = " ".join(strip_md(x) for x in sample_a)
    else:
        sample_a_txt = strip_md(str(sample_a))

    if indic(slug):
        return [
            {
                "t": "S",
                "m": "2",
                "q": f"“{title}” का केंद्रीय बिंदु 20–30 शब्दों में लिखिए।",
                "a": idea_short,
            },
            {
                "t": "L",
                "m": "5",
                "q": f"“{title}” को विस्तार से समझाइए और एक परीक्षा-उदाहरण दीजिए।",
                "a": [
                    idea_short,
                    f"अंक-दृष्टि: {lens[:280]}",
                    f"याद रखने की युक्ति: {trick[:240]}",
                ],
            },
            {
                "t": "A",
                "m": "3",
                "q": (
                    f"रीना कक्षा 10 की परीक्षा की तैयारी कर रही है। पाठ “{title}” "
                    f"({short or 'पाठ का मुख्य विचार'}) पर आधारित एक स्थिति यह है: "
                    f"एक विद्यार्थी ने यह गलती की — {mistake} "
                    f"सही विधि लिखिए और बताइए कि अंक क्यों कटते हैं।"
                ),
                "a": [
                    f"सही विधि: {trick}",
                    f"अंक कटने का कारण: {mistake}",
                    "उत्तर में परिभाषा + उदाहरण दोनों लिखें।",
                ],
            },
            {
                "t": "A",
                "m": "3",
                "q": (
                    f"अमित को यह प्रश्न मिला: “{sample_q}” "
                    f"इसे अनुप्रयोग प्रश्न की तरह 3 अंकों में बिंदुवार हल कीजिए।"
                ),
                "a": sample_a_txt[:700],
            },
            {
                "t": "C",
                "m": "4",
                "q": (
                    f"निम्नलिखित स्थिति पढ़कर उत्तर दीजिए।\n\n"
                    f"कक्षा 10 की एक छात्रा “{title}” का पुनरावलोकन कर रही है। "
                    f"उसने नोट किया: {idea[:280]}\n\n"
                    f"(क) इस पाठ का मुख्य विचार क्या है?\n"
                    f"(ख) बोर्ड में यह विचार कैसे पूछा जाता है?\n"
                    f"(ग) एक ऐसी गलती बताइए जिससे अंक कटते हैं।"
                ),
                "a": [
                    f"(क) {short or idea_short}",
                    f"(ख) {lens[:300]}",
                    f"(ग) {mistake}",
                ],
            },
            {
                "t": "C",
                "m": "4",
                "q": (
                    f"केस पढ़ें और उत्तर दें।\n\n"
                    f"दो मित्र एक ही प्रश्न हल कर रहे हैं: “{sample_q}” "
                    f"एक मित्र केवल एक पंक्ति लिखता है, दूसरा बिंदु और उदाहरण देता है।\n\n"
                    f"(क) पूर्ण अंक के लिए उत्तर-ढाँचा क्या होना चाहिए?\n"
                    f"(ख) आदर्श उत्तर के मुख्य बिंदु लिखिए।"
                ),
                "a": [
                    "(क) परिभाषा / कथन → तर्क या विधि → उदाहरण या निष्कर्ष।",
                    f"(ख) {sample_a_txt[:500]}",
                ],
            },
        ]

    return [
        {
            "t": "S",
            "m": "2",
            "q": f"In 20–30 words, state the central idea of “{title}” and one fact the board always asks.",
            "a": idea_short,
        },
        {
            "t": "L",
            "m": "5",
            "q": (
                f"Discuss “{title}” in detail. Include the idea that carries marks, "
                f"one worked example or answer frame, and why students lose marks."
            ),
            "a": [
                idea_short,
                f"Marks lens: {lens[:320]}",
                f"Method / memory trick: {trick[:280]}",
                f"Do not: {mistake}",
            ],
        },
        {
            "t": "A",
            "m": "3",
            "q": (
                f"Riya is revising “{title}” ({short or 'this topic'}). "
                f"A classmate lost marks by doing this: {mistake} "
                f"Apply the correct method and rewrite the scoring answer."
            ),
            "a": [
                f"Correct method: {trick}",
                f"Why the mistake costs marks: {mistake}",
                "Write the definition or formula first, then the working or example.",
            ],
        },
        {
            "t": "A",
            "m": "3",
            "q": (
                f"Amit is given this exam-style task from “{title}”: “{sample_q}” "
                f"Treat it as an application question. Identify the idea, then write the working in points."
            ),
            "a": [
                f"Idea: {short or title}.",
                sample_a_txt[:650],
            ],
        },
        {
            "t": "C",
            "m": "4",
            "q": (
                f"Read and answer:\n\n"
                f"A Class 10 student is preparing “{title}”. Their note says: {idea[:300]}\n\n"
                f"The chapter is described as: {short or 'high-yield if the answer frame is followed'}.\n\n"
                f"(a) Name the key idea.\n"
                f"(b) How is this usually asked in the paper?\n"
                f"(c) State one mistake that would cost a mark."
            ),
            "a": [
                f"(a) {short or idea_short}",
                f"(b) {lens[:320]}",
                f"(c) {mistake}",
            ],
        },
        {
            "t": "C",
            "m": "4",
            "q": (
                f"Read and answer:\n\n"
                f"Two students attempt: “{sample_q}” "
                f"Student A writes one line. Student B writes points, an example and a check.\n\n"
                f"(a) Which answer frame should you use for full marks?\n"
                f"(b) Write the model points.\n"
                f"(c) Add one memory trick you would use on exam morning."
            ),
            "a": [
                "(a) Statement → working or reasons in points → example or check. One-line answers lose step marks.",
                f"(b) {sample_a_txt[:500]}",
                f"(c) {trick}",
            ],
        },
    ]


def extra_mcq(ch: dict, slug: str) -> list[dict]:
    title = ch.get("title", "this chapter")
    short = strip_md(ch.get("short") or title)
    if indic(slug):
        return [
            {
                "q": f"“{title}” का सबसे उपयोगी पुनरावलोकन क्या है? (a) केवल शीर्षक पढ़ना  (b) मुख्य बिंदु + एक उदाहरण  (c) पूरा पाठ बिना नोट्स  (d) केवल MCQ",
                "a": "**(b) मुख्य बिंदु + एक उदाहरण।** बोर्ड उत्तर-ढाँचे पर अंक देता है।",
            },
            {
                "q": f"इस पाठ का सार है: {short[:80]}. सही कथन चुनें। (a) उदाहरण की आवश्यकता नहीं  (b) परिभाषा पर्याप्त है  (c) परिभाषा के साथ उदाहरण/विधि लिखें  (d) केवल चित्र बनाएँ",
                "a": "**(c) परिभाषा के साथ उदाहरण/विधि लिखें।**",
            },
        ]
    return [
        {
            "q": (
                f"The most exam-ready way to revise “{title}” is: "
                f"(a) read the heading only  (b) learn the key idea plus one example  "
                f"(c) skip written practice  (d) memorise a random extra topic"
            ),
            "a": f"**(b) learn the key idea plus one example.** The chapter is {short}.",
        },
        {
            "q": (
                f"A 3-mark answer on “{title}” should: "
                f"(a) be one sentence  (b) start with the idea, then a reason or method  "
                f"(c) copy the whole chapter  (d) leave the example out"
            ),
            "a": "**(b) start with the idea, then a reason or method.** Step marks follow that frame.",
        },
    ]


def enrich_chapter(ch: dict, slug: str) -> bool:
    changed = False
    qa = list(ch.get("qa") or [])
    for q in qa:
        t = infer_type(q)
        if q.get("t") != t:
            q["t"] = t
            changed = True

    counts = {k: 0 for k in "SLAC"}
    for q in qa:
        counts[q["t"]] = counts.get(q["t"], 0) + 1

    extras = extras_for(ch, slug)
    have_q = {str(q.get("q", "")).strip() for q in qa}
    for extra in extras:
        if counts.get(extra["t"], 0) >= 2:
            continue
        if extra["q"] in have_q:
            continue
        qa.append(extra)
        have_q.add(extra["q"])
        counts[extra["t"]] = counts.get(extra["t"], 0) + 1
        changed = True

    ch["qa"] = qa

    mcq = list(ch.get("mcq") or [])
    if len(mcq) < 5:
        existing = {m.get("q") for m in mcq}
        for item in extra_mcq(ch, slug):
            if item["q"] not in existing:
                mcq.append(item)
                existing.add(item["q"])
                changed = True
        ch["mcq"] = mcq
    return changed


def main() -> None:
    n_files = n_ch = 0
    for path in sorted(CH_DIR.glob("*/*.json")):
        slug = path.parent.name
        data = json.loads(path.read_text(encoding="utf-8"))
        chapters = data if isinstance(data, list) else [data]
        file_changed = False
        for ch in chapters:
            if enrich_chapter(ch, slug):
                file_changed = True
                n_ch += 1
        if file_changed:
            path.write_text(
                json.dumps(chapters if isinstance(data, list) else chapters[0], ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            n_files += 1
            print(f"updated {path.relative_to(ROOT)}")
    print(f"enriched {n_ch} chapters in {n_files} files")


if __name__ == "__main__":
    main()
