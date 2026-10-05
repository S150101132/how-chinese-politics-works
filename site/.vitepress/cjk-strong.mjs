export function cjkStrong(md) {
  md.inline.ruler.before('emphasis', 'cjk-strong', (state, silent) => {
    const match = /^\*\*([^\n]+?)\*\*/.exec(state.src.slice(state.pos));
    if (!match) return false;
    if (!silent) {
      state.push('strong_open', 'strong', 1);
      const inner = [];
      state.md.inline.parse(match[1], state.md, state.env, inner);
      state.tokens.push(...inner);
      state.push('strong_close', 'strong', -1);
    }
    state.pos += match[0].length;
    return true;
  });
}
