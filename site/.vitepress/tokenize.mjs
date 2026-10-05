// Adjacent Han pairs match phrases inside continuous Chinese prose.
// Index and query must use this same tokenizer; no external search service.
export function tokenize(text) {
  const tokens = [];
  for (const match of text.toLowerCase().matchAll(/[\p{Script=Han}]+|[\p{L}\p{N}]+/gu)) {
    const word = match[0];
    if (/^\p{Script=Han}+$/u.test(word)) {
      const chars = Array.from(word);
      if (chars.length === 1) tokens.push(word);
      else for (let i = 0; i < chars.length - 1; i++) tokens.push(chars[i] + chars[i + 1]);
    } else tokens.push(word);
  }
  return tokens;
}
