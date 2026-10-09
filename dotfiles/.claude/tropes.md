# AI Writing Tropes to Avoid

Sources: [AI writing tropes](https://gist.github.com/ossa-ma/f3baa9d25154c33095e22272c631f5a1), Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), and [load-bearing](https://github.com/louisabraham/load-bearing), a cluster analysis of 461,121 GitHub pull request descriptions.

Each trope below is a pattern to avoid. The quoted lines under it show the pattern.

## Word Choice

### "Quietly" and Other Magic Adverbs

Adverbs that make a mundane description feel significant or understated: "quietly", "deeply", "fundamentally", "remarkably", "arguably".

- "quietly orchestrating workflows, decisions, and interactions"

### "Honestly" and "Genuinely"

Sincerity markers that imply everything else was less than honest: "honest", "honestly", "honesty", "genuinely", "to be fair", "frankly", "let's be real". Same family: performative emotion staged for weight ("I say this in anger", "I resent"). Strip them out and the sentence loses nothing.

- "This is a genuinely hard problem."

### "Delve" and Friends

Overused AI vocabulary: "delve", "certainly", "utilize", "leverage" (as a verb), "robust", "streamline", "harness", "pivotal", "crucial", "intricate", "underscore", "garner", "showcase", "meticulous", "foster", "synthesize", "surface" (as a verb), "unpack" outside the "Let's unpack" framing, and "enhance" with its whole conjugation ("enhanced", "enhancing", "enhancements"): the word adds approval without saying what changed.

- "We certainly need to leverage these robust frameworks..."

### "Tapestry" and "Landscape"

Ornate or grandiose nouns where a simpler word does the job: "tapestry" for anything interconnected, "landscape" for any field or domain, "paradigm", "synergy", "ecosystem", "framework".

- "Navigating the complex landscape of modern AI..."

### Brochure Puffery

Travel-guide and press-release vocabulary applied to anything at all: "vibrant", "nestled in the heart of", "groundbreaking", "renowned", "boasts a", "rich cultural heritage", "stunning natural beauty", "must-visit", "diverse array", "commitment to". Enthusiasm adjectives with no information in them: "amazing", "incredible", "perfect". Product-marketing compounds: "enterprise-grade", "production-ready", "community-driven", "ai-powered". "-ability" nouns that promise virtue without a mechanism: "modularity", "maintainability", "scalability", "flexibility".

- "A vibrant community offering a diverse array of tools."

### Latin Abbreviations

"e.g.," and "i.e.," in place of plain English. Write "like" for "e.g.,": it reads faster, and a parenthetical "(e.g., X, Y)" reads like a footnote dropped mid-sentence, while "(like X or Y)" flows naturally. For "i.e.,", inline the clarification.

Avoid:

- "Use a linter (e.g., Ruff or Flake8) to catch issues early."
- "Some formats (i.e., CSV) lack a schema."

Prefer:

- "Use a linter like Ruff or Flake8 to catch issues early."
- "Some formats (CSV, TSV) lack a schema."

### The "Serves As" Dodge

"serves as", "stands as", "marks" or "represents" in place of a plain "is" or "are".

- "The building serves as a reminder of the city's heritage."

### Elegant Variation

Synonyms cycled to avoid repeating a word: the festival becomes "the event", then "the celebration", then "the gathering". The reader keeps re-deriving that they are the same thing. Repeat the word.

- "The bug was reported Monday. The issue was triaged Tuesday. The defect was fixed Wednesday."

### "Load-Bearing" and Other Engineering Metaphors

Mechanical and structural metaphors that dress prose up as rigorous systems analysis. Structure: "load-bearing", "tension", "gated", "guarded against", "pushing back" (usually "gently"). Ops and planning: "blast radius", changes "land", "spine", "seams", "grammar", plans "bake", "cutover", "long pole", boundaries "dissolve", outcomes "sealed", ideas "earn their keep", "register", "grain", "floor", "ladder". Legal and accounting: "premise", "ruling", "carve-out", "ceiling", "owed". Machinery and plumbing: "backstop", "chokepoint", "lever", "wedged", "stamped". Personified code: it "refuses" input, "carries" responsibility, "survives" refactors. Literal technical uses are fine (a guard clause, a feature gate, tension in a cable, a version floor, a patch landing on a branch): the tell is the metaphorical spread into ordinary prose. In the load-bearing corpus, this style went from 0.7% of everything written at the start of 2025 to 39% by mid-2026, and "load-bearing" is the single most distinctive word of the corpus.

- "That comment is load-bearing: the whole abstraction leans on it."
- "This change lands behind a gate to keep the blast radius small."
- "The whole system rests on that premise."
- "Only the parser survived the refactor."

### Agile Ceremony Jargon

Sprint-planning vocabulary in prose that has no scrum in it: "sprint", "epic", "story points", "stand-up", "retro", "grooming". Use the plain word: iteration, feature, estimate, meeting, review.

- "Let's take this to the next retro."

## Sentence Structure

### Negative Parallelism

The "It's not X -- it's Y" pattern, often with an em dash: false profundity that frames everything as a surprising reframe. The most commonly identified AI tell. One in a piece can work. Variants: the causal "not because X, but because Y", the em-dash dismissal "X -- not Y", the cross-sentence reframe "The question isn't X. The question is Y.", the additive "not only X, but also Y" and the emphasis flip "X rather than Y".

- "It's not bold. It's backwards."

### "Not X. Not Y. Just Z."

The dramatic countdown: two or more negations before the actual point.

- "Not a bug. Not a feature. A fundamental design flaw."

### "The X? A Y."

A rhetorical question nobody asked, answered at once for dramatic effect.

- "The result? Devastating."

### Anaphora Abuse

The same sentence opening repeated several times in quick succession.

- "They assume that users will pay... They assume that developers will build... They assume that ecosystems will emerge... They assume that..."

### Tricolon Abuse

The rule of three, overused or extended to four or five items. One tricolon is elegant. Three back to back are a pattern.

- "Products impress people; platforms empower them. Products solve problems; platforms create worlds. Products scale linearly; platforms scale exponentially."
- "identity, payments, compute, distribution"

### "It's Worth Noting"

Filler transitions that connect nothing: "It's worth noting", "It bears mentioning", "Importantly", "Interestingly", "Notably". Hedge transitions that announce what the sentence already delivers: "To be clear", "That said".

- "It's worth noting that this approach has limitations."

### Superficial Analyses

A present participle ("-ing") phrase at the end of a sentence that attaches significance, legacy or broader meaning to a mundane fact: "highlighting its importance", "reflecting broader trends", "contributing to the development of...".

- "underscoring its role as a dynamic hub of activity and culture"

### False Ranges

"from X to Y" where X and Y are on no real scale with a meaningful middle: a fancy way to list loosely related things.

- "From innovation to implementation to cultural transformation."

### Gerund Fragment Litany

A claim followed by a stream of verbless gerund fragments, standalone sentences with no subject. They add only word count.

- "Fixing small bugs. Writing straightforward features. Implementing well-defined tickets."

## Paragraph Structure

### Short Punchy Fragments

Very short sentences or fragments as standalone paragraphs, for manufactured emphasis.

- "He published this. Openly. In a book. As a priest."

### Listicle in a Trench Coat

A list disguised as prose: each paragraph starts with "The first...", "The second...", "The third...".

- "The first wall is the absence of a free, scoped API... The second wall is the lack of delegated access... The third wall is the absence of scoped permissions..."

## Tone

### "Here's the Kicker"

False suspense before an unremarkable point: "Here's the kicker", "Here's the thing", "Here's where it gets interesting", "Here's what most people miss", "Here's the starting point", "Here's the deal", and the caveat variant "One caveat, and it's a real one".

- "Here's the thing about AI adoption."

### "Think of It As..."

The patronizing analogy: "Think of it as...", "It's like a...". It assumes the reader needs a metaphor, and the analogy is often less clear than the concept.

- "Think of it as a Swiss Army knife for your workflow."

### "Imagine a World Where..."

An invitation to futurism: "Imagine", then a list of wonderful things that happen if the reader agrees with the premise.

- "Imagine a world where every tool you use -- your calendar, your inbox, your documents, your CRM, your code editor -- has a quiet intelligence behind it..."

### False Vulnerability

Simulated self-awareness or honesty: the writer pretends to break the fourth wall or to admit a bias. Real vulnerability is specific and uncomfortable. Also firsthand experience the writer cannot have: "I've seen this pattern take down production systems many times."

- "And yes, I'm openly in love with the platform model"

### "The Truth Is Simple"

A statement that the point is obvious, clear or simple, in place of the proof. Also the reveal variant: "but none of them is the real story. The real story is...".

- "History is clear, the metrics are clear, the examples are clear"

### False Precision

Diagnostic confidence without the diagnosis: a guess labeled "the root cause", a hunch labeled "the key insight", an approximation wrapped in "exactly" or "precisely". Certainty adverbs that close a case nobody opened: "plainly", "outright", "merely", "provably", "empirically". Check-claiming compounds that report a verification the writer never ran: "byte-identical", "bit-identical", "mutation-checked". Human hedging ("seems", "perhaps", "probably") is falling out of PR prose while this vocabulary takes its place.

- "The root cause is a race condition in the scheduler."
- "The two outputs are byte-identical, so the rewrite is provably safe."

### Rigor-Washing Adjectives

Self-praise adjectives that claim rigor without showing it: "comprehensive", "rigorous", "systematic", "surgical", "elegant".

- "A surgical fix that elegantly resolves the issue."

### Grandiose Stakes Inflation

Every argument inflated to world-historical significance.

- "This will fundamentally reshape how we think about everything."

### "A Testament To..."

Unearned significance vocabulary that awards every subject a legacy: "stands as a testament", "cemented its legacy", "a pivotal moment", "left an indelible mark", "deeply rooted", "setting the stage for", "continues to captivate", "garnered significant attention".

- "The release marked a pivotal moment that cemented the project's legacy."

### Staged Gravity

Phrases that stop the prose to announce that something matters: "the moment", "in one breath", "the thing itself", "near and dear".

- "In one breath it promises speed, and in the next it takes it away."

### "Let's Break This Down"

The pedagogical voice that assumes the reader needs hand-holding, even an expert one: "Let's break this down", "Let's unpack this", "Let's explore", "Let's dive in". Also "deep-dive" and "unpack" as standalone synonyms for "look at" and "explain".

- "Let's break this down step by step."

### "No Action Required"

Reassurance about what the reader does not have to do: a step or a section that closes by naming what is not needed, not required, or will happen without the reader. Also the pitch variant, a benefit listed as absences. Keep a negative statement only when it changes what the reader does: a warning against a wrong action ("Do not squash-merge"), the consequence of skipping a step ("Without the key, releases skip the scan"), or, in reference docs, a fact about how a mechanism works ("Cloudflare never builds the site").

- "No action is required. This issue will close automatically."
- "It installs each tool at a pinned version: no manual setup, no dotfile sprawl."

### Vague Attributions

Claims attributed to unnamed authorities: "experts", "observers", "industry reports", "several publications". Also an inflated count of sources: what one person said, presented as a widely held view. If you can't name the expert, you don't have a source.

- "Experts argue that this approach has significant drawbacks."

### Invented Concept Labels

Invented compound labels used as if they were established terms: an abstract problem-noun (paradox, trap, creep, divide, vacuum, inversion) appended to a domain word. They name a thing and skip the argument.

- "the supervision paradox"
- "the acceleration trap"
- "workload creep"

## Formatting

### Em-Dash Addiction

Em dashes for dramatic pauses, parenthetical asides and pivot points: a human writer uses 2-3 per piece, AI uses 20+. The same compulsion continues as stacked parenthetical asides (nested (sometimes twice)).

- "The problem -- and this is the part nobody talks about -- is systemic."

### Bold-First Bullets

Every list item starts with a bolded phrase, often with emojis. The same tic bolds random key phrases mid-paragraph.

- "**Security**: Environment-based configuration with..."

### Unicode Decoration

Use of unicode arrows (->), smart/curly quotes, and other special characters that can't be easily typed on a standard keyboard. Real writers typing in a text editor produce straight quotes and -> or =>.

- "Input → Processing → Output"
- "“Smart quotes” instead of straight "quotes" that you’d actually type"

### Structural Tics

Document-shape giveaways: Title Case On Every Heading, a horizontal rule before each section, emoji as bullet markers or heading decorations, heading levels that jump from H2 to H4, and a gratuitous comparison table where a sentence would do. Each is defensible alone. Together they make a page look like a filled-in template.

- "🚀 Features / ⚡ Performance / 🔒 Security"

## Composition

### Fractal Summaries

"What I'm going to tell you; what I'm telling you; what I just told you", applied at every level: each subsection, each section and the document get a summary.

- "In this section, we'll explore... [3000 words later] ...as we've seen in this section."

### The Dead Metaphor

One metaphor repeated 5-10 times across the piece. Introduce a metaphor, use it, then move on.

- "The ecosystem needs ecosystems to build ecosystem value."

### Historical Analogy Stacking

A rapid list of historical companies or tech revolutions that builds false authority. Especially common in technical writing.

- "Apple didn't build Uber. Facebook didn't build Spotify. Stripe didn't build Shopify. AWS didn't build Airbnb."

### One-Point Dilution

One argument restated in ten ways, with different metaphors, examples and framings, to feel comprehensive.

- "The same point, restated eight ways across 4000 words."

### Every Route at Once

Every way to do a thing, where the reader needs one: "or run this, or use the dashboard, or the other form works too", each route with its own caveat. Give the route to take, plus at most one fallback, and leave the others to the reference docs.

- "Or `wrangler pages project create`, or the dashboard: Workers & Pages → Direct Upload."

### Content Duplication

Whole sections or paragraphs repeated in the same piece, verbatim or reworded.

- "Paragraph 3 and paragraph 17 are the same sentence reworded"

### The Signposted Conclusion

The conclusion announced: "In conclusion", "To sum up", "In summary".

- "To sum up, we've explored three key themes..."

### "Despite Its Challenges..."

The formula "Despite its [positive words], [subject] faces challenges...", closed by "Despite these challenges, [optimistic conclusion].". Also boilerplate closing sections titled "Challenges and Future Prospects" or "Future Outlook".

- "Despite these challenges, the initiative continues to thrive."

## Artifacts

### Chat Residue

Chatbot correspondence in the deliverable: openers, closers and offers addressed to a user who isn't there ("I hope this helps!", "Certainly!", "Of course!", "You're absolutely right!", "Would you like me to...", "Let me know if..."). Same family: knowledge-cutoff disclaimers ("as of my last knowledge update", "not widely documented in available sources"), unfilled placeholders ("[Your Name]", "INSERT_SOURCE_URL", "2025-XX-XX"), and machine markup droppings like "oaicite", "turn0search0" and "contentReference".

- "I hope this helps! Let me know if you'd like a more detailed breakdown."

### Fabricated Citations

References that look right and aren't: URLs that 404, DOIs and ISBNs that don't resolve or land on unrelated papers, book citations with no page numbers, sources that don't contain the claim they're attached to. A "utm_source=chatgpt.com" query parameter in a link is a confession. Only cite what you actually opened.

- "A plausible paper title with a DOI that resolves to a different article"

### Invented Facts

Plausible specifics with no source behind them: a version number nobody looked up, a line count nobody ran, a "typical" latency, "I've seen this pattern before". The specific number reads as evidence, so the reader stops checking. Keep the facts, names and numbers you were given and invent none unless asked. Say "unknown" where you do not know.

- "This takes about 200ms on a typical machine."

Any of these patterns used once might be fine. The problem is when multiple tropes appear together or when a single trope is used repeatedly. Write like a human: varied, imperfect, specific.
