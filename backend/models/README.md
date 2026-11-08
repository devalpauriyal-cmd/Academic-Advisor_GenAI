# Bundled embedding model

Upstream: [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).

The local ONNX model and tokenizer match the upstream file metadata at revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, checked on 8 November 2026. The ONNX file was checked against its LFS SHA-256; the tokenizer was checked against its Git blob SHA-1. The original download date was not recorded.

The upstream model metadata declares Apache-2.0. The standard license text from https://www.apache.org/licenses/LICENSE-2.0.txt is included as `all-MiniLM-L6-v2/LICENSE`; no separate upstream LICENSE file was present at the checked revision. This license does not cover the university documents or this project as a whole.

| Local file | Bytes | SHA-256 |
| --- | ---: | --- |
| `all-MiniLM-L6-v2/model.onnx` | 90405214 | `6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452` |
| `all-MiniLM-L6-v2/tokenizer.json` | 466247 | `be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037` |

These assets remain committed to preserve existing API startup/deployment behavior. `backend/embedder.py` performs tokenization, mean pooling and L2 normalization with ONNX Runtime; no PyTorch dependency is required.
