# Model catalogue: starting candidates

Status: proposal, 2026-11-18. This is research, not a result. Which models end up recommended is decided by the evaluation in docs/EVAL.md. The setup command shows a model's name, size and licence before downloading it.

How this was gathered: Ollama library pages and Hugging Face model cards, read on 2026-11-18 by fetching the pages. Sizes are the download sizes Ollama lists. They are not runtime memory: running a model needs the weights plus a context cache that grows with context length, plus overhead. Measure that in milestone M4 instead of estimating it.

## Candidates

| Model (Ollama tag) | Download | Context | Tool calling | Licence, and where it was read |
|---|---|---|---|---|
| qwen3:1.7b | 1.4 GB | 40K | yes (also lists thinking) | Apache 2.0, Hugging Face card (the Qwen3 4B and 8B cards were read, not the 1.7B card itself) |
| qwen3:4b | 2.5 GB | 256K | yes | Apache 2.0, Hugging Face card |
| qwen3:8b | 5.2 GB (the default tag) | 40K | yes | Apache 2.0, Hugging Face card |
| qwen3:14b | 9.3 GB | 40K | yes | not read; assume nothing until checked |
| phi4-mini:3.8b | 2.5 GB | 128K | yes | MIT, Hugging Face card |
| qwen2.5:7b | 4.7 GB | 32K | yes | Apache 2.0, stated on the Ollama page |
| mistral:7b | 4.4 GB | 32K | yes | "Apache license", stated on the Ollama page |
| nomic-embed-text (embeddings only) | 274 MB | 2K | not applicable | Apache 2.0, Hugging Face card |

Speech, for the later milestone: Whisper is MIT (GitHub licence file), `faster-whisper` is MIT (repository sidebar), and the `Systran/faster-whisper-small` weights are marked MIT on Hugging Face.

## Left out of the default list, and why

- **llama3.2 (1b, 3b):** tool calling yes, 128K context, but the licence is the Llama 3.2 Community License, and the model is gated on Hugging Face. As written on the card: a "Built with Llama" notice, "Llama" at the start of the name of any model distributed or improved with its outputs, an Acceptable Use Policy, and a licence request above 700 million monthly active users. That is manageable for a user who downloads it themselves, but it puts obligations on a project that distributes or fine-tunes it. Offer it as an opt-in with a notice, not as a default.
- **gemma3:** the Ollama page shows vision, not a tools label, and names the Gemma Terms of Use without giving their text. The terms were not read. Not a default until both are checked.
- **qwen2.5:3b:** the Ollama readme says the 3B and 72B models are under the Qwen licence, while the others are Apache 2.0. The Qwen licence was not read.
- **smollm3:** Apache 2.0 on Hugging Face, but the Ollama library page returned 404 on 2026-11-18, so it would need a manual model import. Later, if at all.

## Proposed starting tiers (to be confirmed or overturned by the evaluation)

| Profile | Candidates to evaluate |
|---|---|
| CPU only, or under about 6 GB free memory | qwen3:1.7b, phi4-mini:3.8b |
| 6 to 8 GB of free GPU memory | qwen3:4b, qwen3:8b, qwen2.5:7b |
| 12 GB or more | qwen3:14b, if its licence checks out |

On this machine the 8 GB card had 1.8 to 2.2 GB in use by other apps when measured for screenvoice, which leaves roughly 6 GB. A 5.2 GB download plus a context cache may not fit. That is a real test, not an assumption either way.

## Open questions

1. Qwen3 lists a thinking mode. It may help or cost a lot of tokens and time on tool tasks. Check Ollama's documentation for the switch, and run it on and off as part of the evaluation.
2. The Qwen3 14B licence and the Qwen3 1.7B card were not read.
3. Quantization level per tag is not stated on the pages read. The catalogue should record it once measured.
4. Models change quickly. The catalogue is a data file with a date on each entry, so an old entry is visibly old.

## Sources

- Ollama library pages: qwen3, qwen2.5, llama3.2, gemma3, phi4-mini, mistral, nomic-embed-text (ollama.com/library/...)
- Hugging Face cards: Qwen/Qwen3-8B, Qwen/Qwen3-4B, meta-llama/Llama-3.2-3B-Instruct, microsoft/Phi-4-mini-instruct, nomic-ai/nomic-embed-text-v1.5, HuggingFaceTB/SmolLM3-3B, Systran/faster-whisper-small
- github.com/openai/whisper (LICENSE), github.com/SYSTRAN/faster-whisper
