import pandas as pd


INPUT_PATH = "outputs/recipe_intelligence.csv"
OUTPUT_PATH = "outputs/recipe_intelligence_with_summary.csv"


FRICTION_HIGH = 0.20
MODIFICATION_HIGH = 0.10
STRONG_MODIFICATION = 0.40
REPEAT_INTENT_HIGH = 0.20


def clean_phrase(value):
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None

    return text


def normalize_pct(value):
    if pd.isna(value):
        return 0.0

    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    # Handles cases where values are stored as percentages like 73.33 instead of 0.7333
    if value > 1:
        value = value / 100.0

    return value


def format_issue(issue):
    issue = clean_phrase(issue)
    if not issue:
        return None

    issue = issue.lower().strip()

    # Keep common friction phrases natural
    if issue.startswith("too "):
        return issue

    if issue in {
        "bland",
        "dry",
        "burnt",
        "curdled",
        "salty",
        "sweet",
        "greasy",
        "watery",
        "dense",
        "mushy",
        "runny",
        "rubbery",
        "tough",
    }:
        return issue

    return issue


def format_fix(phrase):
    phrase = clean_phrase(phrase)
    if not phrase:
        return None

    phrase = phrase.lower().strip()

    if phrase.startswith("added "):
        return "adding " + phrase[len("added "):]

    if phrase.startswith("add "):
        return "adding " + phrase[len("add "):]

    if phrase.startswith("reduce "):
        return "reducing " + phrase[len("reduce "):]

    if phrase.startswith("reduced "):
        return "reducing " + phrase[len("reduced "):]

    if phrase.startswith("used "):
        return "using " + phrase[len("used "):]

    if phrase.startswith("substitute "):
        return "substituting " + phrase[len("substitute "):]

    if phrase.startswith("substituted "):
        return "substituting " + phrase[len("substituted "):]

    if phrase.startswith("swap "):
        return "swapping " + phrase[len("swap "):]

    if phrase.startswith("swapped "):
        return "swapping " + phrase[len("swapped "):]

    if phrase.startswith("double "):
        return "doubling " + phrase[len("double "):]

    if phrase.startswith("doubled "):
        return "doubling " + phrase[len("doubled "):]

    if phrase.startswith("halve "):
        return "halving " + phrase[len("halve "):]

    if phrase.startswith("halved "):
        return "halving " + phrase[len("halved "):]

    return phrase


def append_repeat_intent(summary, pct_repeat_intent):
    if pct_repeat_intent >= REPEAT_INTENT_HIGH:
        return summary + " Despite this, many users still indicate they would make it again."
    return summary


def generate_summary(row):
    pct_friction = normalize_pct(row.get("pct_friction", 0))
    pct_modification = normalize_pct(row.get("pct_modification", 0))
    pct_repeat_intent = normalize_pct(row.get("pct_repeat_intent", 0))

    top_friction = issue_phrase(row.get("top_friction_phrase_1"))
    top_modification = format_fix(row.get("top_modification_phrase_1"))

    total_comments = row.get("total_comments", 0) or 0
    has_behavioral_signal = row.get("has_behavioral_signal", 1)

    if total_comments < 5 or has_behavioral_signal == 0:
        return "Low signal: not enough reliable user feedback to identify a clear issue."

    # High friction + strong modification = users clearly see the problem and are actively fixing it
    if pct_friction >= FRICTION_HIGH and pct_modification >= STRONG_MODIFICATION:
        if top_friction and top_modification:
            summary = (
                f"This recipe has consistent issues with {top_friction}, "
                f"but many users fix it by {top_modification}."
            )
        elif top_friction:
            summary = (
                f"This recipe has consistent issues with {top_friction}, "
                f"and users are frequently modifying it, but no clear fix pattern stands out."
            )
        else:
            summary = (
                "This recipe shows clear user friction, and many users are actively modifying it, "
                "but no single fix stands out."
            )
        return append_repeat_intent(summary, pct_repeat_intent)

    # High friction + some modification = some adaptation, but less consistent
    if pct_friction >= FRICTION_HIGH and pct_modification >= MODIFICATION_HIGH:
        if top_friction and top_modification:
            summary = (
                f"This recipe has recurring issues with {top_friction}, "
                f"and some users adapt it by {top_modification}."
            )
        elif top_friction:
            summary = (
                f"This recipe has recurring issues with {top_friction}, "
                f"and users are frequently modifying it, but no clear fix pattern stands out."
            )
        else:
            summary = (
                "This recipe shows clear user friction, and users appear to be finding workarounds."
            )
        return append_repeat_intent(summary, pct_repeat_intent)

    # High friction + low modification = problem is clear, fix is not
    if pct_friction >= FRICTION_HIGH and pct_modification < MODIFICATION_HIGH:
        if top_friction:
            summary = (
                f"This recipe has recurring complaints about {top_friction}, "
                f"and users are not converging on a reliable fix."
            )
        else:
            summary = (
                "This recipe shows meaningful user friction, and users are not converging on a reliable fix."
            )
        return append_repeat_intent(summary, pct_repeat_intent)

    # Low friction + high modification = recipe is flexible more than broken
    if pct_friction < FRICTION_HIGH and pct_modification >= STRONG_MODIFICATION:
        if top_modification:
            summary = (
                f"Users frequently adapt this recipe by {top_modification}, "
                f"even though strong complaints are limited."
            )
        else:
            summary = (
                "Users frequently adapt this recipe in different ways, "
                "even though strong complaints are limited."
            )
        return append_repeat_intent(summary, pct_repeat_intent)

    if pct_friction < FRICTION_HIGH and pct_modification >= MODIFICATION_HIGH:
        if top_modification:
            summary = (
                f"Some users adjust this recipe by {top_modification}, "
                f"though strong complaints are limited."
            )
        else:
            summary = (
                "Some users adjust this recipe, though strong complaints are limited."
            )
        return append_repeat_intent(summary, pct_repeat_intent)

    # Fallbacks
    if top_friction:
        summary = (
            f"This recipe is generally stable, though some users mention issues with {top_friction}."
        )
        return append_repeat_intent(summary, pct_repeat_intent)

    if top_modification:
        summary = (
            f"This recipe performs relatively well, though users sometimes adjust it by {top_modification}."
        )
        return append_repeat_intent(summary, pct_repeat_intent)

    return "This recipe performs relatively well with no clear recurring issue or user fix pattern."

def issue_phrase(issue):
    issue = clean_phrase(issue)
    if not issue:
        return None

    issue = issue.lower().strip()

    if issue.startswith("too "):
        return issue

    adjective_issues = {
        "bland",
        "dry",
        "burnt",
        "curdled",
        "salty",
        "sweet",
        "greasy",
        "watery",
        "dense",
        "mushy",
        "runny",
        "rubbery",
        "tough",
    }

    if issue in adjective_issues:
        return f"being {issue}"

    return issue

def main():
    df = pd.read_csv(INPUT_PATH)

    df["summary"] = df.apply(generate_summary, axis=1)

    df.to_csv(OUTPUT_PATH, index=False)

    preview_cols = [
        "recipe_id",
        "title",
        "pct_friction",
        "pct_modification",
        "pct_repeat_intent",
        "top_friction_phrase_1",
        "top_modification_phrase_1",
        "summary",
    ]

    preview_cols = [col for col in preview_cols if col in df.columns]

    print(df[preview_cols].head(10).to_string(index=False))
    print(f"\nSaved file: {OUTPUT_PATH}")

    print("\nTop 10 High Opportunity Recipes:\n")

    top = (
        df[df["classification"] == "High Opportunity"]
        .sort_values("opportunity_score", ascending=False)
        .head(10)
    )

    cols = [
        "title",
        "pct_friction",
        "pct_modification",
        "top_friction_phrase_1",
        "top_modification_phrase_1",
        "summary",
    ]

    cols = [c for c in cols if c in top.columns]

    print(top[cols].to_string(index=False))


if __name__ == "__main__":
    main()