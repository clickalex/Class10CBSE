# 08 · Sanskrit (Code 122)

**Only if Sanskrit is your Language II.** If not, delete this folder.

- **Theory:** 80 marks · **Internal assessment:** 20 marks · **Time:** 3 hours
- **Prescribed books:** शेमुषी भाग-2 (main reader) and अभ्यासवान् भव / व्याकरण
  (workbook–grammar)

## What is here

```
08-Sanskrit/
├── 02-NCERT-Textbook/
│   ├── Shemushi-Bhag-2/
│   └── Abhyasvan-Bhav/
├── 03-Notes/
│   ├── Shemushi-Bhag-2/      lesson notes go here
│   ├── Vyakaran/             संधि, समास, प्रत्यय, विभक्ति, अव्यय, अनुवाद
│   └── Lekhan/               पत्रलेखन, अनुच्छेदलेखन, संवादलेखन
├── 04-NCERT-Solutions/
├── 05-Important-Questions/
├── 06-Practice-Worksheets/
├── 07-Previous-Year-Questions/
├── 08-Sample-Papers/
└── 09-Revision-Sheets/
```

## Why lesson folders are not pre-created

The lesson list for शेमुषी भाग-2 varies between editions, and I did not verify
it against an official source, so I left the lesson folders out rather than
guess. When you have the book in hand, add the lessons to
`scripts/structure.conf`:

```
08-Sanskrit/03-Notes/Shemushi-Bhag-2/patha01-Name-Of-Lesson
08-Sanskrit/03-Notes/Shemushi-Bhag-2/patha02-Name-Of-Lesson
```

then run `scripts/build_structure.sh`.

## Where the marks are

Sanskrit is largely scoring: श्लोक with अन्वय and भावार्थ, अनुवाद, पदच्छेद,
and a solid व्याकरण section. Keep a `shlok.md` per lesson in
`03-Notes/Shemushi-Bhag-2/` with the श्लोक, अन्वय, शब्दार्थ and भावार्थ on one
page — that single file covers most of the literature questions for that lesson.
