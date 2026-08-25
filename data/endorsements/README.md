# Endorsements corpus

Drop the **6 supplied endorsement files** here. `.pdf`, `.txt`, and `.md` are all read.

```
HO-0304-ed-03-24.pdf
HO-0417-ed-05-24.pdf
...
```

**Only these 6 get indexed.** Do not re-index the whole policy wording library —
the ingest is plumbing, the measurement is the deliverable.

The loader pulls four fields off each file's header, falling back to the filename:

| field | parsed from |
| ----- | ----------- |
| `source_file` | the filename |
| `form_number` | `HO-####` in the first 1500 chars, else the filename |
| `edition_date` | `ed. MM-YY` in the header, else `Effective:` line, else the filename |
| `policy_line` | a `Policy_line:` line, else inferred from the text |

If a field comes back `UNKNOWN`, fix the header or the regex in
[loader.py](../../backend/app/ingestion/loader.py) — an `UNKNOWN` is a failed
ingest and `ingest.py` will refuse to index it.
