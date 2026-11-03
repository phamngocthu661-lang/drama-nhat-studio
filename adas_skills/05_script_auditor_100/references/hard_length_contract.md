# HARD SCRIPT LENGTH CONTRACT — v2.0

This contract is mandatory across the entire workflow.

## Valid final range
A final narration script is valid only when:

- `PURE_CHARACTER_COUNT >= 40,001`
- `PURE_CHARACTER_COUNT <= 50,000`

`40,000` exactly is **NOT sufficient**. The minimum is **40,001**.

## What counts as a pure character
Normalize text to Unicode NFC, then count only Unicode categories whose first letter is:
- `L` = letters (Kanji, Hiragana, Katakana, Latin letters, etc.)
- `N` = numbers

Exclude from the count:
- punctuation
- symbols
- spaces
- tabs
- line breaks
- markdown punctuation / quotation marks
- emoji and decorative marks

In Python, the canonical rule is:

```python
sum(1 for ch in unicodedata.normalize("NFC", text)
    if unicodedata.category(ch)[0] in {"L", "N"})
```

## Hard gate
- `<= 40,000` → **FAIL_LENGTH_GATE**
- `40,001–50,000` → **PASS_LENGTH_GATE**
- `> 50,000` → **FAIL_LENGTH_GATE**

A script that fails this gate may still be diagnosed, but it may NOT be marked `READY_FOR_AUDIT`, `PUBLISH_READY`, or allowed into STEP 6.

## Target zone
Write toward **44,000–47,000 pure characters** so later edits do not accidentally drop below the hard minimum or exceed the maximum.

## Expansion quality rule
Never pad length with repetition, duplicated moral lessons, redundant flashbacks, paraphrases of the same emotion, or empty dialogue. Extra length must perform at least one story function: new clue, new decision, new consequence, motivation, relationship shift, setup, payoff, escalating risk, or meaningful aftermath.
