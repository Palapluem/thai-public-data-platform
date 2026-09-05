# Public snapshot provenance

These files are deterministic local snapshots for development, testing and
portfolio demonstration. They are not a claim that the source websites will
remain unchanged or that these are the newest releases after the retrieval
date. The registry is [`../../config/public_sources.yml`](../../config/public_sources.yml).

## Directory layout

```text
public/
├── finance/mof/       # CSV, nested JSON API and HTML table
├── labour/nso/        # tabular JSON
└── derived/labour/    # canonical Parquet materialization
```

Folders describe the business domain and source owner. The registry's
`format`, `parser` and `source_role` fields describe how the file should be
read and whether it is authoritative, validation-only or derived.

| File | Format | Rows parsed | SHA-256 |
|---|---|---:|---|
| `finance/mof/budget_summary_2568.csv` | CSV | 2,985 input / 5,969 canonical metrics | `6f4b134205e0b33a6d42de31b967caa4e5df400eac1658c902f1fdba86307620` |
| `finance/mof/budget_monthly_2026.json` | nested JSON API | 675 | `4f9419e0f1a689aa0ff86a94ca933e6b4fde49aeaeaba5c6e86305dfb131cf90` |
| `finance/mof/budget_summary_2026.html` | HTML table | 67 | `ddd5a95f60503a6e5fedc361dcd3f0a1ae05b3ff76622c48e899121790fb2b04` |
| `labour/nso/labour_region_sex_2569.json` | tabular JSON | 350 | `72407d6bbdfa87e9d2fa3f4a1fa5e21802d5104a4a84b21041594e9262241834` |
| `derived/labour/nso_labour_region_sex_2569.parquet` | derived Parquet | 350 | generated locally |

## Official references

- [DGA Government Spending dataset](https://data.go.th/dataset/gfsummary)
- [Ministry of Finance Data Services](https://dataservices.mof.go.th/menu4?id=3&lang=en)
- [NSO labour-force dataset](https://data.go.th/en/dataset/0706_02_0001)

The CSV came from the public data catalog resource, the nested JSON came from
the Ministry of Finance documented API, the HTML came from its published data
services table, and the NSO JSON came from the catalog API resource documented
on the dataset page.

## Refresh workflow

1. download a new file/API response to a new path;
2. calculate SHA-256 and record retrieval/source-updated time;
3. profile and parse without discarding raw evidence;
4. update the registry only after checking the source URL and expected grain;
5. run parser, DQ, integration and dashboard checks;
6. keep the old release so a backfill or correction remains explainable.

Do not overwrite a checked-in baseline casually: a changed file with the same
filename is a new release and must receive a new hash and evidence.
