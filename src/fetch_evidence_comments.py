import pandas as pd

INPUT_PATH = "outputs/comment_signals.csv"
OUTPUT_PATH = "outputs/evidence_comment_samples.csv"

# Minimum conditions
MIN_LENGTH = 40   # avoid tiny comments
MAX_LENGTH = 500  # avoid extremely long comments

SAMPLE_SIZE = 200  # total rows to inspect


def load_data():
    df = pd.read_csv(INPUT_PATH)
    print(f"Loaded {len(df)} rows")
    return df


def filter_comments(df):
    # Basic filtering
    df = df[
        (df["eligible_for_analysis"] == 1)
        & (df["clean_comment_text"].notnull())
    ].copy()

    # Length filter
    df["comment_length"] = df["clean_comment_text"].str.len()
    df = df[
        (df["comment_length"] >= MIN_LENGTH)
        & (df["comment_length"] <= MAX_LENGTH)
    ]

    print(f"After length + eligibility filter: {len(df)}")

    return df


def select_signal_comments(df):
    # Keep comments with friction OR modification signals
    df = df[
        (df["signal_friction"] == 1)
        | (df["signal_modification"] == 1)
        | (df["signal_substitution"] == 1)
    ].copy()

    print(f"After signal filter: {len(df)}")

    return df


def add_signal_labels(df):
    def get_signal_type(row):
        if row["signal_friction"] == 1 and (
            row["signal_modification"] == 1 or row["signal_substitution"] == 1
        ):
            return "mixed"
        elif row["signal_friction"] == 1:
            return "issue"
        else:
            return "fix"

    df["signal_type"] = df.apply(get_signal_type, axis=1)
    return df


def sample_data(df):
    # Stratified sample: issue / fix / mixed
    samples = []

    for signal_type in ["issue", "fix", "mixed"]:
        subset = df[df["signal_type"] == signal_type]

        if len(subset) == 0:
            continue

        n = min(SAMPLE_SIZE // 3, len(subset))
        samples.append(subset.sample(n=n, random_state=42))

    sampled_df = pd.concat(samples)
    print(f"Final sampled rows: {len(sampled_df)}")

    return sampled_df


def main():
    df = load_data()
    df = filter_comments(df)
    df = select_signal_comments(df)
    df = add_signal_labels(df)
    df = sample_data(df)

    # Select useful columns
    out = df[
        [
            "recipe_id",
            "clean_comment_text",
            "signal_type",
            "signal_friction",
            "signal_modification",
            "signal_substitution",
        ]
    ].copy()

    out.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()