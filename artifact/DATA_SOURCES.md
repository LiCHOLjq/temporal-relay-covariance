# Experimental inputs and attribution

Each input is the original compressed byte stream from the Stanford Large Network Dataset Collection. The five files in the sibling `raw_input_cache/` are preserved for local scholarly replay. Sources were checked on 23 November 2026. Cite Jure Leskovec and Andrej Krevl, *SNAP Datasets*, and the relevant source work on each dataset page. [SNAP collection and citation](https://snap.stanford.edu/data/) · [SNAP attribution instructions](https://snap.stanford.edu/citing.html)

| Source file | Data and original source |
| --- | --- |
| CollegeMsg.txt.gz | Directed timestamped messages among college students. SNAP identifies Tore Opsahl's original dataset and cites Panzarasa, Opsahl and Carley. [CollegeMsg](https://snap.stanford.edu/data/CollegeMsg.html) |
| email-Eu-core-temporal.txt.gz | Directed temporal email within a European research institution. [SNAP source and citation](https://snap.stanford.edu/data/email-Eu-core-temporal.html) |
| soc-sign-bitcoinotc.csv.gz | Timestamped, weighted directed trust ratings on Bitcoin OTC. [SNAP source and citation](https://snap.stanford.edu/data/soc-sign-bitcoin-otc.html) |
| soc-sign-bitcoinalpha.csv.gz | Timestamped, weighted directed trust ratings on Bitcoin Alpha. [SNAP source and citation](https://snap.stanford.edu/data/soc-sign-bitcoin-alpha.html) |
| sx-mathoverflow-a2q.txt.gz | Answers-to-questions relation from MathOverflow. [SNAP source and citation](https://snap.stanford.edu/data/sx-mathoverflow.html) |

The measured code retains directed non-self events, preserves repeated events and groups by supplied timestamps. The relay queries ignore Bitcoin rating magnitude. The source manifests report original sizes and hashes, and the run records the transformations and removed self events. [Five source checksums](snap_sources.json) · [Main-run records](experiments/results/run.json) · [MathOverflow records](experiments/results/sql.json)

The dataset pages provide public downloads and citation guidance. A separate, explicit redistribution license for these exact compressed files was not verified. The SNAP BSD notice pertains to its software. Before publishing a copy of the private input cache with a paper, confirm the applicable rights for each dataset. The portable artifact contains a verified retrieval program and can be shared separately from that cache, subject to the rights in its contents. [SNAP software license](https://snap.stanford.edu/snap/license.html)
