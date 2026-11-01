# Kosh evaluation

agent: 18 questions, naive: 18 questions

| Metric | Target | agent | naive |
|---|---|---|---|
| Answer correct | ≥ 0.8 | 0.92 ✅ | 0.92 ✅ |
| Source chunk retrieved | ≥ 0.8 | 0.75 ❌ | 0.75 ❌ |
| Faithfulness (self-check) | ≥ 0.85 | 0.93 ✅ | 0.93 ✅ |
| Valid citations | ≥ 0.95 | 1.0 ✅ | 1.0 ✅ |
| Correct refusals | ≥ 0.9 | 1.0 ✅ | 1.0 ✅ |
| Wrong refusals | ≤ 0.1 | 0.0 ✅ | 0.0 ✅ |
| p95 seconds | ≤ 8.0 | 170.4 ❌ | 169.4 ❌ |
