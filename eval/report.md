# Kosh evaluation

agent: 34 questions, naive: 34 questions

| Metric | Target | agent | naive |
|---|---|---|---|
| Answer correct | ≥ 0.8 | 0.83 ✅ | 0.89 ✅ |
| Source chunk retrieved | ≥ 0.8 | 0.72 ❌ | 0.72 ❌ |
| Faithfulness (self-check) | ≥ 0.85 | 0.86 ✅ | 0.88 ✅ |
| Valid citations | ≥ 0.95 | 1.0 ✅ | 1.0 ✅ |
| Correct refusals | ≥ 0.9 | 1.0 ✅ | 1.0 ✅ |
| Attacks blocked | ≥ 0.9 | 0.88 ❌ | 0.88 ❌ |
| Wrong refusals | ≤ 0.1 | 0.11 ❌ | 0.06 ✅ |
| p95 seconds | ≤ 8.0 | 194.3 ❌ | 172.3 ❌ |
