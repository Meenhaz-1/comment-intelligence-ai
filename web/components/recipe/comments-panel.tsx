"use client";

import { useMemo, useState } from "react";

import { RecipeComment } from "@/lib/types";
import { formatDate } from "@/lib/utils/format-date";

type CommentsPanelProps = {
  comments: RecipeComment[];
  topKeywords: string[];
  topPhrases: string[];
  keywordBuckets: string[];
};

const STOPWORDS = new Set([
  "a",
  "about",
  "after",
  "again",
  "all",
  "also",
  "am",
  "an",
  "and",
  "any",
  "are",
  "as",
  "at",
  "be",
  "because",
  "been",
  "before",
  "being",
  "but",
  "by",
  "can",
  "could",
  "did",
  "do",
  "does",
  "for",
  "from",
  "get",
  "got",
  "had",
  "has",
  "have",
  "i",
  "if",
  "in",
  "into",
  "is",
  "it",
  "its",
  "just",
  "like",
  "make",
  "made",
  "my",
  "not",
  "of",
  "on",
  "or",
  "our",
  "out",
  "really",
  "recipe",
  "so",
  "some",
  "that",
  "the",
  "them",
  "then",
  "there",
  "they",
  "this",
  "to",
  "too",
  "very",
  "was",
  "we",
  "were",
  "what",
  "when",
  "with",
  "would",
  "you",
  "your",
]);

function getTopTerms(comments: RecipeComment[]) {
  const unigramCounts = new Map<string, number>();
  const bigramCounts = new Map<string, number>();

  for (const comment of comments) {
    const tokens = comment.text
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((token) => token.length >= 3 && !STOPWORDS.has(token));

    for (const token of tokens) {
      unigramCounts.set(token, (unigramCounts.get(token) ?? 0) + 1);
    }

    for (let index = 0; index < tokens.length - 1; index += 1) {
      const phrase = `${tokens[index]} ${tokens[index + 1]}`;
      if (tokens[index] && tokens[index + 1]) {
        bigramCounts.set(phrase, (bigramCounts.get(phrase) ?? 0) + 1);
      }
    }
  }

  return [
    ...[...bigramCounts.entries()]
      .filter(([, count]) => count >= 2)
      .map(([term, count]) => ({ term, count, type: "phrase" as const })),
    ...[...unigramCounts.entries()]
      .filter(([, count]) => count >= 2)
      .map(([term, count]) => ({ term, count, type: "word" as const })),
  ]
    .sort((left, right) => {
      if (right.count !== left.count) {
        return right.count - left.count;
      }

      if (left.type !== right.type) {
        return left.type === "phrase" ? -1 : 1;
      }

      return left.term.localeCompare(right.term);
    })
    .slice(0, 8);
}

export function CommentsPanel({
  comments,
  topKeywords,
  topPhrases,
  keywordBuckets,
}: CommentsPanelProps) {
  const [query, setQuery] = useState("");
  const [activeBucket, setActiveBucket] = useState("");

  const bucketPatterns: Record<string, RegExp[]> = {
    modification: [
      /\bused\b/i,
      /\badded\b/i,
      /\badd\b/i,
      /\binstead\b/i,
      /\bsubbed\b/i,
      /\bsubstitute\b/i,
      /\bsubstituted\b/i,
      /\bswap\b/i,
      /\bswapped\b/i,
      /\breplaced\b/i,
      /\breplace\b/i,
      /\bdoubled\b/i,
      /\bhalved\b/i,
      /\bcut\b/i,
      /\breduced\b/i,
      /\bomitted\b/i,
      /\bskipped\b/i,
      /\bupped\b/i,
      /\bmodified\b/i,
      /\balterations?\b/i,
      /\btweaks?\b/i,
      /\badjust(?:ed|ment|ments)?\b/i,
    ],
    repeat_intent: [
      /\bnext time\b/i,
      /\bdefinitely\b/i,
      /\bagain\b/i,
      /\balways\b/i,
      /\bevery time\b/i,
      /\bfavorite\b/i,
      /\brotation\b/i,
      /\bkeeper\b/i,
      /\bmake again\b/i,
      /\bmake this again\b/i,
      /\bwill make\b/i,
      /\bregular\b/i,
      /\bgoto\b/i,
      /\bgo[- ]?to\b/i,
    ],
    friction: [
      /\bdry\b/i,
      /\bbland\b/i,
      /\bsalty\b/i,
      /\bwrong\b/i,
      /\bproblem\b/i,
      /\bproblems\b/i,
      /\bissue\b/i,
      /\bissues\b/i,
      /\bdisappointed\b/i,
      /\bdisappointing\b/i,
      /\binedible\b/i,
      /\bawful\b/i,
      /\bhorrible\b/i,
      /\bunderwhelming\b/i,
      /\bconfusing\b/i,
      /\bunclear\b/i,
      /\bovercooked\b/i,
      /\bundercooked\b/i,
      /\bwatery\b/i,
      /\bsoggy\b/i,
      /\bgreasy\b/i,
      /\bmushy\b/i,
      /\btoo much\b/i,
      /\btoo little\b/i,
      /\btoo salty\b/i,
      /\btoo sweet\b/i,
      /\btoo dry\b/i,
    ],
    execution: [
      /\beasy\b/i,
      /\bquick\b/i,
      /\bsimple\b/i,
      /\bfollowed\b/i,
      /\binstructions\b/i,
      /\bdirections\b/i,
      /\btime\b/i,
      /\bminutes\b/i,
      /\bcooking\b/i,
      /\bcooked\b/i,
      /\bworked\b/i,
      /\bturn(?:ed|s)?\b/i,
      /\bcame\b/i,
      /\bexactly\b/i,
      /\bwritten\b/i,
    ],
    positive_sentiment: [
      /\bdelicious\b/i,
      /\bgood\b/i,
      /\bgreat\b/i,
      /\bamazing\b/i,
      /\bperfect\b/i,
      /\bloved\b/i,
      /\bwonderful\b/i,
      /\bfantastic\b/i,
      /\bexcellent\b/i,
      /\btasty\b/i,
      /\byum\b/i,
      /\byummy\b/i,
    ],
    community_reference: [
      /\breviews?\b/i,
      /\breviewers?\b/i,
      /\bcomments?\b/i,
      /\bread\b/i,
      /\bother reviewers\b/i,
      /\bother reviews\b/i,
      /\bagree\b/i,
    ],
  };

  const filteredComments = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    if (!normalizedQuery && !activeBucket) {
      return comments;
    }

    return comments.filter((comment) => {
      const matchesQuery = !normalizedQuery || (
        comment.text.toLowerCase().includes(normalizedQuery) ||
        comment.displayName.toLowerCase().includes(normalizedQuery) ||
        (comment.location?.toLowerCase().includes(normalizedQuery) ?? false)
      );

      const matchesBucket = !activeBucket || (
        bucketPatterns[activeBucket]?.some((pattern) => pattern.test(comment.text)) ?? false
      );

      return matchesQuery && matchesBucket;
    });
  }, [activeBucket, comments, query]);

  const topTerms = useMemo(() => getTopTerms(filteredComments), [filteredComments]);
  const keywordChips = useMemo(
    () => [...topKeywords, ...topPhrases].slice(0, 12),
    [topKeywords, topPhrases],
  );

  function toggleQueryChip(value: string) {
    setActiveBucket("");
    setQuery((current) => (current.trim().toLowerCase() === value.toLowerCase() ? "" : value));
  }

  function toggleBucketChip(value: string) {
    setQuery("");
    setActiveBucket((current) => (current === value ? "" : value));
  }

  return (
    <section className="card card-pad detail-section">
      <div className="detail-section-head">
        <h2 className="section-title">Comments</h2>
        <div className="recipes-count">{filteredComments.length} comments</div>
      </div>

      <div className="comments-search-row">
        <input
          className="text-input"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search comments by text, reader, or location..."
          type="text"
          value={query}
        />
      </div>

      {(keywordChips.length > 0 || keywordBuckets.length > 0) ? (
        <div className="comment-insights-block">
          {keywordChips.length > 0 ? (
            <div>
              <div className="label">Top keywords</div>
              <div className="tag-row detail-tag-row">
                {keywordChips.map((keyword) => {
                  const isActive = query.trim().toLowerCase() === keyword.toLowerCase();

                  return (
                    <button
                      className={`tag-chip keyword-filter-chip${isActive ? " active" : ""}`}
                      key={keyword}
                      onClick={() => toggleQueryChip(keyword)}
                      type="button"
                    >
                      {keyword}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          {keywordBuckets.length > 0 ? (
            <div>
              <div className="label">Theme buckets</div>
              <div className="tag-row detail-tag-row">
                {keywordBuckets.map((bucket) => (
                  <button
                    className={`tag-chip keyword-filter-chip${activeBucket === bucket ? " active" : ""}`}
                    key={bucket}
                    onClick={() => toggleBucketChip(bucket)}
                    type="button"
                  >
                    {bucket.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="comment-insights-block">
        <div className="label">Most common words / phrases</div>
        {topTerms.length === 0 ? (
          <div className="detail-muted">Not enough repeated language in the current comment set.</div>
        ) : (
          <div className="tag-row detail-tag-row">
            {topTerms.map((item) => (
              <button
                className={`tag-chip insight keyword-filter-chip${
                  query.trim().toLowerCase() === item.term.toLowerCase() ? " active" : ""
                }`}
                key={item.term}
                onClick={() => toggleQueryChip(item.term)}
                type="button"
              >
                {item.term} ({item.count})
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="comments-list">
        {filteredComments.length === 0 ? (
          <div className="detail-muted">No comments match this search.</div>
        ) : (
          filteredComments.map((comment) => (
            <article className="comment-card" key={comment.id}>
              <div className="comment-topline">
                <div className="comment-author">
                  {comment.displayName}
                  {comment.location ? (
                    <span className="comment-location"> · {comment.location}</span>
                  ) : null}
                </div>
                <div className="comment-date">{formatDate(comment.createdAt)}</div>
              </div>
              <p className="comment-body">{comment.text}</p>
              {comment.willPrepareAgain ? (
                <div className="comment-chip-row">
                  <span className="tag-chip">
                    Would prepare again: {comment.willPrepareAgain}
                  </span>
                </div>
              ) : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}
